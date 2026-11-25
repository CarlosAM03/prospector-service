import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from .schemas import utc_now

TTL = timedelta(minutes=60)


@dataclass(frozen=True)
class Snapshot:
    id: str
    data: bytes
    expires_at: datetime
    deadline: float


class Snapshots:
    def __init__(self, quota: int, max_size: int, max_count: int):
        self.quota = quota
        self.max_size = max_size
        self.max_count = max_count
        self.total = 0
        self.items = {}

    def add(self, key, data: bytes):
        if (
            len(data) > self.max_size
            or self.total + len(data) > self.quota
            or len(self.items) >= self.max_count
        ):
            return None
        snapshot = Snapshot(
            str(uuid4()), data, utc_now() + TTL, time.monotonic() + TTL.total_seconds()
        )
        self.items[key] = snapshot
        self.total += len(data)
        return snapshot

    def remove(self, key):
        snapshot = self.items.pop(key, None)
        if snapshot:
            self.total -= len(snapshot.data)
        return snapshot

    def due(self):
        now = time.monotonic()
        return [key for key, snapshot in self.items.items() if snapshot.deadline <= now]
