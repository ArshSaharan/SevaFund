"""Tamper-evident audit log (hybrid v4, development only).

Every decision, information request, confirmation attempt and state change is appended as an entry whose hash
covers its content and the previous entry's hash.  Changing, removing or reordering any entry breaks `verify()`.
This makes the record auditable; it is not a substitute for write-once storage in production.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from pydantic import BaseModel, Field

GENESIS = "0" * 64


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def case_fingerprint(case: dict) -> str:
    """Hash of the campaign input exactly as assessed (title, story, amounts, documents ...)."""
    return sha256(canonical(case))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEntry(BaseModel):
    seq: int
    at: datetime
    actor: str
    event: str
    data: dict = Field(default_factory=dict)
    prev_hash: str
    hash: str


def _entry_hash(seq: int, at: datetime, actor: str, event: str, data: dict, prev_hash: str) -> str:
    return sha256(canonical({"seq": seq, "at": at.isoformat(), "actor": actor, "event": event, "data": data,
                             "prev_hash": prev_hash}))


class AuditLog(BaseModel):
    entries: List[AuditEntry] = Field(default_factory=list)

    def append(self, actor: str, event: str, data: Optional[dict] = None,
               clock: Optional[Callable[[], datetime]] = None) -> AuditEntry:
        at = (clock or utcnow)()
        data = json.loads(canonical(data or {}))           # store exactly what was hashed
        prev = self.entries[-1].hash if self.entries else GENESIS
        seq = len(self.entries)
        entry = AuditEntry(seq=seq, at=at, actor=actor, event=event, data=data, prev_hash=prev,
                           hash=_entry_hash(seq, at, actor, event, data, prev))
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = GENESIS
        for seq, entry in enumerate(self.entries):
            if entry.seq != seq or entry.prev_hash != prev or \
                    entry.hash != _entry_hash(entry.seq, entry.at, entry.actor, entry.event, entry.data, entry.prev_hash):
                return False
            prev = entry.hash
        return True

    @property
    def head(self) -> str:
        return self.entries[-1].hash if self.entries else GENESIS
