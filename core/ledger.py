import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field

GENESIS_PREV_HASH = "0" * 64


class LedgerEntry(BaseModel):
    seq: int
    timestamp: AwareDatetime
    actor: str
    kind: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str = ""


def _hash_of(entry: LedgerEntry) -> str:
    content = json.dumps(
        {
            "seq": entry.seq,
            "timestamp": entry.timestamp.isoformat(),
            "actor": entry.actor,
            "kind": entry.kind,
            "payload": entry.payload,
            "prev_hash": entry.prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class HashChainLedger(BaseModel):
    entries: list[LedgerEntry] = Field(default_factory=list)

    def append(self, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
        entry = LedgerEntry(
            seq=len(self.entries) + 1,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            kind=kind,
            payload=payload,
            prev_hash=self.entries[-1].hash if self.entries else GENESIS_PREV_HASH,
        )
        entry.hash = _hash_of(entry)
        self.entries.append(entry)
        return entry

    def verify(self) -> int | None:
        prev_hash = GENESIS_PREV_HASH
        for entry in self.entries:
            if entry.prev_hash != prev_hash or entry.hash != _hash_of(entry):
                return entry.seq
            prev_hash = entry.hash
        return None
