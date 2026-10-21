import asyncio
import threading

import httpx
import pytest

from prospector_service.adapters.callbacks import CallbackClient
from prospector_service.errors import EngineExecutionError
from prospector_service.jobs import JobService
from prospector_service.schemas import BusinessResult, JobStatus, StartJobRequest

from .conftest import FakeEngine, another


@pytest.mark.parametrize(
    "failure,expected",
    [
        (EngineExecutionError("ENGINE_EXTRACTION_FAILED"), "ENGINE_EXTRACTION_FAILED"),
        (RuntimeError("unsafe"), "ENGINE_UNEXPECTED_ERROR"),
    ],
)
async def test_failure_does_not_kill_worker(settings, payload, callbacks, failure, expected):
    engine = FakeEngine(failure=failure)
    service = JobService(settings, engine, CallbackClient(settings, transport=callbacks[1]))
    await service.start()
    try:
        await service.accept(StartJobRequest(**payload))
        await asyncio.wait_for(service.queue.join(), 3)
        first = service.registry[payload["jobId"]]
        assert first.status is JobStatus.FAILED
        assert first.events[-1].error.code == expected
        engine.failure = None
        second = another(payload, 3)
        await service.accept(StartJobRequest(**second))
        await asyncio.wait_for(service.queue.join(), 3)
        assert service.registry[second["jobId"]].status is JobStatus.COMPLETED
        assert not service.worker.done()
    finally:
        await service.stop()


async def test_serial_thread_execution_and_job_isolation(settings, payload, callbacks):
    engine = FakeEngine()
    service = JobService(settings, engine, CallbackClient(settings, transport=callbacks[1]))
    loop_thread = threading.get_ident()
    await service.start()
    try:
        first, second = payload, another(payload, 3)
        second["tenantId"] = "c" + "8" * 24
        await service.accept(StartJobRequest(**first))
        await service.accept(StartJobRequest(**second))
        await asyncio.wait_for(service.queue.join(), 3)
        assert len(set(engine.threads)) == 1 and engine.threads[0] != loop_thread
        for body in (first, second):
            job = service.registry[body["jobId"]]
            assert [e.sequence for e in job.events] == [1, 2, 3]
            assert all(e.jobId == body["jobId"] for e in job.events)
        assert service.lookup(first["jobId"], second["tenantId"]) is None
    finally:
        await service.stop()


async def test_callback_failure_does_not_corrupt_engine_outcome(settings, payload):
    callback = CallbackClient(
        settings, transport=httpx.MockTransport(lambda r: httpx.Response(503))
    )
    service = JobService(settings, FakeEngine(), callback)
    await service.start()
    try:
        await service.accept(StartJobRequest(**payload))
        await asyncio.wait_for(service.queue.join(), 3)
        job = service.registry[payload["jobId"]]
        assert job.status is JobStatus.COMPLETED and job.callback_failures == 3
    finally:
        await service.stop()


async def test_runtime_failure_disables_new_acceptance(settings, payload, callbacks):
    engine = FakeEngine(
        failure=EngineExecutionError("ENGINE_RUNTIME_UNAVAILABLE", runtime_unavailable=True)
    )
    service = JobService(settings, engine, CallbackClient(settings, transport=callbacks[1]))
    await service.start()
    try:
        await service.accept(StartJobRequest(**payload))
        await asyncio.wait_for(service.queue.join(), 3)
        assert not service.readiness()["engine_browser_startup_probe"]
    finally:
        await service.stop()


@pytest.mark.parametrize(
    "records",
    [
        tuple(BusinessResult(name=str(i), source="google_maps") for i in range(3)),
        (BusinessResult(name="x" * 2048, source="google_maps"),),
    ],
)
async def test_result_limits_are_not_silently_truncated(settings, payload, callbacks, records):
    settings = settings.model_copy(update={"max_result_bytes": 1024})
    service = JobService(
        settings, FakeEngine(result=records), CallbackClient(settings, transport=callbacks[1])
    )
    await service.start()
    try:
        await service.accept(StartJobRequest(**payload))
        await asyncio.wait_for(service.queue.join(), 3)
        job = service.registry[payload["jobId"]]
        assert job.status is JobStatus.FAILED
        assert job.events[-1].error.code == "RESULT_LIMIT_EXCEEDED"
        assert job.results is None
    finally:
        await service.stop()
