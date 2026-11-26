import hmac
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .auth import Actor
from .errors import ServiceError
from .schemas import AcceptedBatch, BatchRequest, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS control (
    id INTEGER PRIMARY KEY CHECK (id = 1), isolation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
    solution TEXT NOT NULL, tenant TEXT NOT NULL, owner TEXT NOT NULL,
    id TEXT NOT NULL, accepted_at TEXT NOT NULL, active INTEGER NOT NULL,
    replay_until TEXT NOT NULL, idem BLOB, digest BLOB, receipt TEXT NOT NULL,
    PRIMARY KEY (solution, id), UNIQUE (solution, tenant, owner, idem)
);
CREATE INDEX IF NOT EXISTS active_lanes ON batches(solution, active, tenant, owner);
CREATE INDEX IF NOT EXISTS replay_expiration ON batches(replay_until) WHERE idem IS NOT NULL;
CREATE TABLE IF NOT EXISTS jobs (
    solution TEXT NOT NULL, batch_id TEXT NOT NULL, id TEXT NOT NULL,
    position INTEGER NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL,
    sequence INTEGER NOT NULL DEFAULT 0, quality TEXT, availability TEXT,
    ack_at TEXT, error TEXT,
    PRIMARY KEY (solution, id), UNIQUE (solution, batch_id, position),
    FOREIGN KEY (solution, batch_id) REFERENCES batches(solution, id)
);
"""


class CoordinatorLock:
    def __init__(self, path: Path):
        self.file = path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                os.fchmod(self.file.fileno(), 0o600)
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise

    def close(self):
        self.file.close()


def isolation_identity() -> str:
    if sys.platform == "linux":
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return f"{boot}:{os.stat('/proc/self/ns/pid').st_ino}"
    return "unverified"


class Metadata:
    def __init__(self, path: Path, key: bytes):
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.lock = CoordinatorLock(path.with_suffix(path.suffix + ".lock"))
        self.key = key
        self.db = None
        try:
            if sys.platform != "win32":
                descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
                try:
                    os.fchmod(descriptor, 0o600)
                finally:
                    os.close(descriptor)
            self.db = sqlite3.connect(path, timeout=0.25, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            if self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise RuntimeError("SQLite WAL is required")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript(SCHEMA)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def close(self):
        try:
            if self.db is not None:
                self.db.close()
        finally:
            self.lock.close()

    def admit(
        self,
        actor: Actor,
        batch: BatchRequest,
        key: str,
        body: bytes,
        ready: bool,
        max_active_batches: int = 1,
    ):
        now = utc_now()
        timestamp = now.isoformat()
        idem = hmac.digest(self.key, b"idempotency\0" + key.encode(), "sha256")
        digest = hmac.digest(self.key, b"body\0" + body, "sha256")
        scope = (actor.solution, actor.tenant, actor.owner)
        with self.transaction():
            previous = self.db.execute(
                """SELECT receipt, digest FROM batches WHERE solution=? AND tenant=?
                   AND owner=? AND idem=? AND replay_until>?""",
                (*scope, idem, timestamp),
            ).fetchone()
            if previous:
                if not hmac.compare_digest(previous["digest"], digest):
                    raise ServiceError(409, "IDEMPOTENCY_CONFLICT", "Idempotency key already used")
                return AcceptedBatch.model_validate_json(previous["receipt"]), False
            if not ready:
                raise ServiceError(503, "SERVICE_UNAVAILABLE", "Execution is unavailable")
            active = self.db.execute(
                "SELECT tenant, owner FROM batches WHERE solution=? AND active=1", (actor.solution,)
            ).fetchall()
            if any((row["tenant"], row["owner"]) == scope[1:] for row in active):
                raise ServiceError(409, "ACTIVE_BATCH", "User already has an active batch")
            if len(active) >= max_active_batches:
                raise ServiceError(429, "QUOTA_EXCEEDED", "Active batch quota exceeded")
            tenants = {row["tenant"] for row in active}
            if (actor.tenant not in tenants and len(tenants) >= 5) or sum(
                row["tenant"] == actor.tenant for row in active
            ) >= 5:
                raise ServiceError(429, "QUOTA_EXCEEDED", "Active batch quota exceeded")
            self.expire_receipts(now)
            receipt = AcceptedBatch(
                batchId=batch.batchId, jobIds=tuple(job.jobId for job in batch.jobs), acceptedAt=now
            )
            try:
                self.db.execute(
                    "INSERT INTO batches VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
                    (
                        *scope,
                        batch.batchId,
                        timestamp,
                        (now + timedelta(hours=48)).isoformat(),
                        idem,
                        digest,
                        receipt.model_dump_json(),
                    ),
                )
                self.db.executemany(
                    """INSERT INTO jobs (solution, batch_id, id, position, status, updated_at)
                       VALUES (?, ?, ?, ?, 'QUEUED', ?)""",
                    (
                        (actor.solution, batch.batchId, job.jobId, position, timestamp)
                        for position, job in enumerate(batch.jobs)
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ServiceError(
                    409, "ID_CONFLICT", "Batch or job ID already registered"
                ) from exc
        return receipt, True

    def expire_receipts(self, now: datetime):
        self.db.execute(
            """UPDATE batches SET idem=NULL, digest=NULL WHERE idem IS NOT NULL AND replay_until<=?""",
            (now.isoformat(),),
        )

    def lookup(self, actor: Actor, batch_id: str):
        row = self.db.execute(
            "SELECT * FROM batches WHERE solution=? AND tenant=? AND owner=? AND id=?",
            (actor.solution, actor.tenant, actor.owner, batch_id),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "NOT_FOUND", "Resource not found")
        return row

    def jobs(self, solution: str, batch_id: str):
        return self.db.execute(
            "SELECT * FROM jobs WHERE solution=? AND batch_id=? ORDER BY position",
            (solution, batch_id),
        ).fetchall()

    def job(self, actor: Actor, batch_id: str, job_id: str):
        self.lookup(actor, batch_id)
        row = self.db.execute(
            "SELECT * FROM jobs WHERE solution=? AND batch_id=? AND id=?",
            (actor.solution, batch_id, job_id),
        ).fetchone()
        if row is None:
            raise ServiceError(404, "NOT_FOUND", "Resource not found")
        return row

    def update(self, solution: str, job_id: str, timestamp: str, **changes):
        allowed = {"status", "quality", "availability", "error", "ack_at"}
        if not changes.keys() <= allowed:
            raise ValueError("unsupported update")
        columns = ", ".join(f"{name}=?" for name in changes)
        prefix = f"{columns}, " if columns else ""
        return self.db.execute(
            f"""UPDATE jobs SET {prefix} updated_at=?, sequence=sequence+1
                WHERE solution=? AND id=? RETURNING *""",
            (*changes.values(), timestamp, solution, job_id),
        ).fetchone()

    def release(self, solution: str, batch_id: str):
        self.db.execute(
            "UPDATE batches SET active=0 WHERE solution=? AND id=?", (solution, batch_id)
        )

    def recover(self):
        identity = isolation_identity()
        with self.transaction():
            previous = self.db.execute("SELECT isolation FROM control WHERE id=1").fetchone()
            self.db.execute("INSERT OR REPLACE INTO control VALUES (1, ?)", (identity,))
            active = self.db.execute("SELECT 1 FROM batches WHERE active=1 LIMIT 1").fetchone()
            # A new PID namespace alone does not prove that the old container stopped.
            verified = (
                previous
                and identity != "unverified"
                and previous[0] != "unverified"
                and previous[0].split(":")[0] != identity.split(":")[0]
            )
            if active and verified:
                self.db.execute("UPDATE batches SET active=0 WHERE active=1")
            affected = self.db.execute(
                """SELECT * FROM jobs WHERE status IN ('QUEUED','RUNNING','AWAITING_RESULTS')
                   OR availability='AVAILABLE' ORDER BY solution, batch_id, position"""
            ).fetchall()
            recovered = []
            for row in affected:
                if row["availability"] == "AVAILABLE":
                    changes = {"availability": "UNAVAILABLE"}
                    kind = "RESULT_AVAILABILITY_CHANGED"
                else:
                    status = "SKIPPED" if row["status"] == "QUEUED" else "INTERRUPTED"
                    changes = {
                        "status": status,
                        "error": "SERVICE_RESTART",
                        "availability": "UNAVAILABLE",
                    }
                    kind = "TERMINAL"
                recovered.append(
                    (
                        kind,
                        self.update(row["solution"], row["id"], utc_now().isoformat(), **changes),
                    )
                )
        return bool(active and not verified), recovered
