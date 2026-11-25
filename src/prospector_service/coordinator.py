import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable

from prospector_export import ExportError
from pydantic import TypeAdapter

from .adapters.callbacks import CallbackRelay
from .adapters.export import export_results
from .errors import ServiceError
from .metadata import Metadata
from .runner import Execution
from .schemas import BusinessResult, utc_now
from .snapshots import Snapshots

logger = logging.getLogger(__name__)
ROWS = TypeAdapter(tuple[BusinessResult, ...])
TERMINALS = {"COMPLETED", "FAILED", "INTERRUPTED", "SKIPPED"}
QUALITIES = {"SUCCESS", "SUCCESS_WITH_ISSUES", "PARTIAL"}


class Coordinator:
    def __init__(self, settings, runner, relay: CallbackRelay, *, clock: Callable = utc_now):
        key = settings.metadata_key
        self.store = Metadata(
            settings.metadata_path, key.get_secret_value().encode() if key else b""
        )
        self.settings = settings
        self.runner = runner
        self.relay = relay
        self.clock = clock
        self.snapshots = Snapshots(
            settings.snapshot_budget_bytes, settings.max_snapshot_bytes, settings.max_snapshots
        )
        self.lanes = set()
        self.exports = set()
        self.stop = asyncio.Event()
        self.unsafe = False
        self.sweeper = None

    def start(self):
        self.unsafe, recovered = self.store.recover()
        for kind, row in recovered:
            self.relay.offer(row, kind)
        self.sweeper = asyncio.create_task(self._sweep())

    @property
    def ready(self):
        return (
            self.settings.credentials_configured
            and self.runner.supported
            and not self.unsafe
            and not self.stop.is_set()
            and self.sweeper is not None
            and not self.sweeper.done()
        )

    def accept(self, actor, batch, key, body):
        receipt, fresh = self.store.admit(actor, batch, key, body, bool(self.ready))
        if fresh:
            for job in batch.jobs:
                row = self.store.update(actor.solution, job.jobId, self.clock().isoformat())
                self.relay.offer(row, "STATE_CHANGED")
            task = asyncio.create_task(self._execute(actor, batch))
            self.lanes.add(task)
            task.add_done_callback(self.lanes.discard)
        return receipt

    async def _execute(self, actor, batch):
        ordinal = -1
        running = False

        def observe(message):
            nonlocal ordinal, running
            index = message["index"]
            kind = message["type"]
            if type(index) is not int or not 0 <= index < len(batch.jobs):
                raise ValueError("invalid query index")
            job = batch.jobs[index]
            timestamp = message["timestamp"]
            if kind == "running" and not running and index == ordinal + 1:
                ordinal, running = index, True
                row = self.store.update(actor.solution, job.jobId, timestamp, status="RUNNING")
                self.relay.offer(row, "STATE_CHANGED")
            elif kind == "awaiting" and running and index == ordinal:
                running = False
                row = self.store.update(
                    actor.solution, job.jobId, timestamp, status="AWAITING_RESULTS"
                )
                self.relay.offer(row, "STATE_CHANGED")
            elif kind == "progress" and running and index == ordinal:
                row = self.store.update(actor.solution, job.jobId, timestamp)
                self.relay.offer(row, "PROGRESS", progress=message["progress"])
            elif kind != "progress":
                raise ValueError("invalid worker transition")

        try:
            execution = await self.runner.run(batch, observe, self.stop)
        except Exception:
            logger.error("engine_supervision_error")
            execution = Execution(error="SUPERVISOR_FAILURE", clean=False)

        try:
            self._finalize(actor, batch, execution)
            if execution.clean:
                self.store.release(actor.solution, batch.batchId)
            else:
                self.unsafe = True
                logger.error("worker_cleanup_unverified")
        except Exception:
            self.unsafe = True
            logger.error("batch_finalization_failed")

    def _finalize(self, actor, batch, execution):
        frame = execution.result or {}
        entries = frame.get("entries", [])
        interrupted = frame.get("interrupted")
        if (
            not isinstance(entries, list)
            or len(entries) > len(batch.jobs)
            or (
                execution.result is not None
                and interrupted is None
                and len(entries) != len(batch.jobs)
            )
            or (
                interrupted is not None
                and (
                    type(interrupted) is not int
                    or interrupted != len(entries)
                    or interrupted >= len(batch.jobs)
                )
            )
        ):
            entries, interrupted = [], None
        for index, row in enumerate(self.store.jobs(actor.solution, batch.batchId)):
            if row["status"] in TERMINALS:
                continue
            snapshot = None
            changes = {"availability": "UNAVAILABLE"}
            if index < len(entries) and row["status"] in {"RUNNING", "AWAITING_RESULTS"}:
                entry = entries[index]
                if entry["status"] == "COMPLETED" and entry["quality"] in QUALITIES:
                    records = ROWS.validate_python(entry["rows"])
                    if len(records) > batch.jobs[index].query.limit:
                        raise ValueError("invalid result count")
                    data = ROWS.dump_json(records)
                    snapshot = self.snapshots.add((actor.solution, batch.batchId, row["id"]), data)
                    changes.update(status="COMPLETED", quality=entry["quality"])
                    if snapshot:
                        changes["availability"] = "AVAILABLE"
                    else:
                        changes["error"] = "SNAPSHOT_CAPACITY"
                else:
                    changes.update(status="FAILED", error=entry.get("error", "ENGINE_QUERY_FAILED"))
            else:
                started = row["status"] != "QUEUED" or index == interrupted
                changes.update(
                    status="INTERRUPTED" if started else "SKIPPED",
                    error=execution.error if interrupted is None else "ENGINE_INTERRUPTED",
                )
            try:
                terminal = self.store.update(
                    actor.solution, row["id"], self.clock().isoformat(), **changes
                )
            except sqlite3.Error:
                if snapshot:
                    self.snapshots.remove((actor.solution, batch.batchId, row["id"]))
                raise
            self.relay.offer(terminal, "TERMINAL", snapshot=snapshot)

    def status(self, actor, batch_id):
        self.expire()
        batch = self.store.lookup(actor, batch_id)
        jobs = []
        for row in self.store.jobs(actor.solution, batch_id):
            job = {
                "jobId": row["id"],
                "queryIndex": row["position"],
                "status": row["status"],
                "updatedAt": row["updated_at"],
                "sequence": row["sequence"],
                "availability": row["availability"],
                "quality": row["quality"],
                "ackAt": row["ack_at"],
                "errorCode": row["error"],
            }
            snapshot = self.snapshots.items.get((actor.solution, batch_id, row["id"]))
            if snapshot:
                job.update(snapshotId=snapshot.id, expiresAt=snapshot.expires_at.isoformat())
            jobs.append(job)
        return {
            "batchId": batch_id,
            "acceptedAt": batch["accepted_at"],
            "active": bool(batch["active"]),
            "jobs": jobs,
        }

    def get_snapshot(self, actor, batch_id, job_id):
        self.expire()
        row = self.store.job(actor, batch_id, job_id)
        snapshot = self.snapshots.items.get((actor.solution, batch_id, job_id))
        if snapshot is None:
            status = 410 if row["availability"] in {"EXPIRED", "PURGED", "UNAVAILABLE"} else 409
            raise ServiceError(status, "RESULT_UNAVAILABLE", "Result snapshot unavailable")
        return snapshot

    def acknowledge(self, actor, batch_id, job_id):
        self.expire()
        row = self.store.job(actor, batch_id, job_id)
        if row["ack_at"] is not None:
            return {"ackAt": row["ack_at"]}
        self.get_snapshot(actor, batch_id, job_id)
        timestamp = self.clock().isoformat()
        self.store.db.execute(
            "UPDATE jobs SET ack_at=? WHERE solution=? AND id=?",
            (timestamp, actor.solution, job_id),
        )
        return {"ackAt": timestamp}

    def purge(self, actor, batch_id, job_id):
        self.expire()
        row = self.store.job(actor, batch_id, job_id)
        if row["status"] not in TERMINALS:
            raise ServiceError(409, "RESULT_UNAVAILABLE", "Result snapshot unavailable")
        if row["availability"] != "PURGED":
            self._remove((actor.solution, batch_id, job_id), "PURGED")
        return {"availability": "PURGED"}

    def expire(self):
        for key in self.snapshots.due():
            self._remove(key, "EXPIRED")

    def _remove(self, key, availability):
        solution, _, job_id = key
        row = self.store.update(
            solution, job_id, self.clock().isoformat(), availability=availability
        )
        self.snapshots.remove(key)
        self.relay.offer(row, "RESULT_AVAILABILITY_CHANGED")

    async def export(self, actor, batch_id, job_id, format):
        snapshot = self.get_snapshot(actor, batch_id, job_id)
        if len(self.exports) >= self.settings.export_concurrency:
            raise ServiceError(503, "EXPORT_BUSY", "Export capacity unavailable")

        def render(data):
            try:
                return export_results(
                    ROWS.validate_json(data), format, max_bytes=self.settings.max_export_bytes
                )
            except ExportError as exc:
                raise ServiceError(
                    503, "EXPORT_UNAVAILABLE", "Export could not be prepared"
                ) from exc

        task = asyncio.create_task(asyncio.to_thread(render, snapshot.data))
        self.exports.add(task)

        def finished(done):
            self.exports.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _sweep(self):
        while not self.stop.is_set():
            self.expire()
            self.store.expire_receipts(self.clock())
            await asyncio.sleep(1)

    async def close(self):
        self.stop.set()
        if self.sweeper:
            self.sweeper.cancel()
            await asyncio.gather(self.sweeper, return_exceptions=True)
        try:
            await asyncio.gather(*self.lanes, *self.exports, return_exceptions=True)
            await self.relay.close()
        finally:
            self.store.close()


def snapshot_response(snapshot):
    # Rows are already serialized and immutable. Avoid expanding the result into Python objects.
    metadata = json.dumps(
        {"snapshotId": snapshot.id, "expiresAt": snapshot.expires_at.isoformat()}
    ).encode()
    return b'{"success":true,"data":' + snapshot.data + b',"meta":' + metadata + b"}"
