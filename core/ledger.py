import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts.interfaces import Ledger
from contracts.schemas import LedgerEntry

GENESIS_PREV_HASH = "0" * 64
# The kind of the entry that stands in for a line of the file that cannot be read as an entry. It holds no
# hash, so verify names it as the first broken entry. Source: docs/decisions.md, 9 October 2026.
UNREADABLE_KIND = "unreadable"


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
        for position, entry in enumerate(self._entries, start=1):
            # An entry out of its place, as after a line was deleted and the rest rechained, is a break too.
            if entry.seq != position or entry.prev_hash != prev_hash or entry.hash != _hash_of(entry):
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
                for number, line in enumerate(handle, start=1):
                    if line.strip():
                        self._entries.append(self._read(line, number))

    def _read(self, line: str, number: int) -> LedgerEntry:
        """A line of the file as an entry, or, when it is not one, an unreadable entry in its place, so an
        edited file still loads and verify names the line. Source: docs/decisions.md, 9 October 2026."""
        try:
            return LedgerEntry.model_validate_json(line)
        except ValidationError:  # anti-pattern: SILENT-EXCEPT ok, the unreadable entry breaks the chain and verify names it
            previous = self._entries[-1] if self._entries else None
            return LedgerEntry(
                seq=len(self._entries) + 1,
                ts=previous.ts if previous is not None else datetime.now(timezone.utc),
                actor="",
                kind=UNREADABLE_KIND,
                payload={"line": number},
                prev_hash="",
                hash="",
            )

    def append(self, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
        stored = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        return super().append(actor, kind, stored)

    def _store(self, entry: LedgerEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # A file whose last line has no newline, as an editor may save it, gets one first, so the new entry
        # never joins the line before it. Source: the Stage 10 review, 9 October 2026.
        ends_open = False
        if self._path.exists() and self._path.stat().st_size:
            with self._path.open("rb") as handle:
                handle.seek(-1, 2)
                ends_open = handle.read(1) != b"\n"
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if ends_open else "") + entry.model_dump_json() + "\n")
        super()._store(entry)
