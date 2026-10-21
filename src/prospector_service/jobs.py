import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .adapters.callbacks import CallbackClient, CallbackPolicy
from .config import Settings
from .errors import EngineCancelled, EngineExecutionError, ServiceError
from .ports import CancellationControl, EnginePort
from .schemas import (
    AcceptedJob,
    BusinessResult,
    JobEvent,
    JobEventError,
    JobStatus,
    StartJobRequest,
    utc_now,
)

logger = logging.getLogger(__name__)


@dataclass
class Job:
    request: StartJobRequest
    callback_url: str
    accepted_at: datetime
    token: CancellationControl
    status: JobStatus = JobStatus.QUEUED
    events: list[JobEvent] = field(default_factory=list)
    callback_failures: int = 0
    results: tuple[BusinessResult, ...] | None = None


class JobService:
    """Single process, one worker/thread, bounded NON-DURABLE in-memory registry/queue."""

    def __init__(self, settings: Settings, engine: EnginePort, callback: CallbackClient):
        self.settings = settings
        self.engine = engine
        self.callback = callback
        self.policy = CallbackPolicy(settings)
        self.registry: dict[str, Job] = {}
        self.queue: asyncio.Queue[Job | None] = asyncio.Queue(settings.queue_capacity)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prospector-engine")
        self.lock = asyncio.Lock()
        self.worker: asyncio.Task | None = None
        self.engine_available = False
        self.accepting = False

    async def start(self) -> None:
        if self.settings.credentials_configured and self.policy.origin:
            self.engine_available = await asyncio.get_running_loop().run_in_executor(
                self.executor,
                self.engine.probe,
            )
        self.worker = asyncio.create_task(self._work(), name="prospector-single-worker")
        self.accepting = True

    def readiness(self) -> dict[str, bool]:
        return {
            "configuration": bool(self.settings.credentials_configured and self.policy.origin),
            "engine_browser_startup_probe": self.engine_available,
            "worker": bool(self.worker and not self.worker.done() and self.accepting),
            "queue_capacity": not self.queue.full(),
            "registry_capacity": len(self.registry) < self.settings.max_registered_jobs,
        }

    async def accept(self, request: StartJobRequest) -> AcceptedJob:
        if not self.settings.credentials_configured or not self.policy.origin:
            raise ServiceError(503, "SERVICE_UNAVAILABLE", "Job execution capacity is unavailable")
        callback_url = self.policy.resolve(request.callbackUrl, request.jobId)
        async with self.lock:
            if request.jobId in self.registry:
                raise ServiceError(409, "JOB_CONFLICT", "Job identifier is already registered")
            if not all(self.readiness().values()):
                raise ServiceError(
                    503, "SERVICE_UNAVAILABLE", "Job execution capacity is unavailable"
                )
            job = Job(request, callback_url, utc_now(), self.engine.new_token())
            self.registry[request.jobId] = job
            try:
                self.queue.put_nowait(job)
            except asyncio.QueueFull as exc:
                del self.registry[request.jobId]
                raise ServiceError(
                    503, "SERVICE_UNAVAILABLE", "Job execution capacity is unavailable"
                ) from exc
            return AcceptedJob(jobId=request.jobId, acceptedAt=job.accepted_at)

    def lookup(self, job_id: str, tenant_id: str) -> Job | None:
        job = self.registry.get(job_id)
        return job if job and job.request.tenantId == tenant_id else None

    async def _emit(
        self,
        job: Job,
        status: JobStatus,
        *,
        results: tuple[BusinessResult, ...] | None = None,
        error: JobEventError | None = None,
    ) -> None:
        event = JobEvent(
            eventId=uuid4(),
            jobId=job.request.jobId,
            sequence=len(job.events) + 1,
            status=status,
            timestamp=utc_now(),
            progress=None,
            results=results,
            error=error,
        )
        job.status = status
        job.events.append(event)
        try:
            delivered = await self.callback.send(job.callback_url, event)
        except Exception:
            delivered = False
        if not delivered:
            job.callback_failures += 1
            logger.warning("callback_delivery_failed", extra={"status": status.value})

    async def _execute(self, job: Job) -> None:
        await self._emit(job, JobStatus.QUEUED)
        await self._emit(job, JobStatus.RUNNING)
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                self.executor,
                self.engine.execute,
                job.request.query,
                job.token,
            )
            if len(result) > job.request.query.limit:
                raise EngineExecutionError("RESULT_LIMIT_EXCEEDED")
            # Bound retained callback/result data. Reject rather than truncate.
            from pydantic import TypeAdapter

            encoded = TypeAdapter(tuple[BusinessResult, ...]).dump_json(result)
            if len(encoded) > self.settings.max_result_bytes:
                raise EngineExecutionError("RESULT_LIMIT_EXCEEDED")
        except EngineCancelled:
            await self._emit(job, JobStatus.CANCELLED)
        except EngineExecutionError as exc:
            if exc.runtime_unavailable:
                self.engine_available = False
            await self._emit(
                job,
                JobStatus.FAILED,
                error=JobEventError(code=exc.code, message="Job execution failed"),
            )
        except Exception:
            logger.error("job_execution_failed")
            await self._emit(
                job,
                JobStatus.FAILED,
                error=JobEventError(code="ENGINE_UNEXPECTED_ERROR", message="Job execution failed"),
            )
        else:
            job.results = result
            await self._emit(job, JobStatus.COMPLETED, results=result)

    async def _work(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                if job is None:
                    return
                await self._execute(job)
            except Exception:
                self.accepting = False
                logger.error("worker_failed")
                raise
            finally:
                self.queue.task_done()

    async def stop(self) -> None:
        self.accepting = False
        try:
            if self.worker is not None:
                join = asyncio.create_task(self.queue.join())
                done, _ = await asyncio.wait(
                    {join, self.worker},
                    timeout=self.settings.shutdown_grace_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    # Never abandon/kill an active synchronous Engine thread.
                    for job in self.registry.values():
                        if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                            job.token.request_cancel()
                    done, _ = await asyncio.wait(
                        {join, self.worker},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                if self.worker in done:
                    # An internal worker failure must not deadlock shutdown behind queued jobs.
                    while not self.queue.empty():
                        self.queue.get_nowait()
                        self.queue.task_done()
                    join.cancel()
                    await asyncio.gather(join, self.worker, return_exceptions=True)
                else:
                    await self.queue.put(None)
                    await self.worker
        finally:
            self.executor.shutdown(wait=True, cancel_futures=False)
            await self.callback.close()
