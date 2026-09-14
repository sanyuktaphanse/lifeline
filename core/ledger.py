import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from contracts.schemas import LedgerEntry

GENESIS_PREV_HASH = "0" * 64


def _hash_of(entry: LedgerEntry) -> str:
    content = json.dumps(
        {
            "seq": entry.seq,
            "ts": entry.ts.isoformat(),
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
            ts=datetime.now(timezone.utc),
            actor=actor,
            kind=kind,
            payload=payload,
            prev_hash=self.entries[-1].hash if self.entries else GENESIS_PREV_HASH,
            hash="",
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
