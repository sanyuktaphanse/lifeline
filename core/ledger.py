import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.interfaces import Ledger
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


class HashChainLedger(Ledger):
    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def append(self, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
        entry = LedgerEntry(
            seq=len(self._entries) + 1,
            ts=datetime.now(timezone.utc),
            actor=actor,
            kind=kind,
            payload=payload,
            prev_hash=self.head(),
            hash="",
        )
        entry.hash = _hash_of(entry)
        self._store(entry)
        return entry

    def _store(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)

    def verify(self) -> int | None:
        prev_hash = GENESIS_PREV_HASH
        for entry in self._entries:
            if entry.prev_hash != prev_hash or entry.hash != _hash_of(entry):
                return entry.seq
            prev_hash = entry.hash
        return None

    def entries(self) -> list[LedgerEntry]:
        return [entry.model_copy(deep=True) for entry in self._entries]

    def head(self) -> str:
        return self._entries[-1].hash if self._entries else GENESIS_PREV_HASH


class JsonlLedger(HashChainLedger):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                self._entries = [LedgerEntry.model_validate_json(line) for line in handle if line.strip()]

    def append(self, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
        stored = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        return super().append(actor, kind, stored)

    def _store(self, entry: LedgerEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")
        super()._store(entry)
