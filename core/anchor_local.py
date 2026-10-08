import hashlib
import hmac
import json
import os
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.interfaces import Anchor
from core.model_adapter import environment

ANCHOR_SECRET_VAR = "LIFELINE_ANCHOR_SECRET"
DEVELOPMENT_ANCHOR_SECRET = "lifeline-development-anchor-secret-not-for-production"
LOCAL = "local"
FISCO = "fisco"
# Source: .env.example. ANCHOR names where the ledger head is anchored; empty means local.
ANCHOR_KINDS = (LOCAL, FISCO)
# A head hash and a user hash are both SHA 256 digests as the ledger writes them, lowercase hex.
DIGEST = re.compile(r"[0-9a-f]{64}")
LINE_FIELDS = ("head_hash", "seq", "user_hash", "anchored_at", "signature")


class AnchorNotConfigured(RuntimeError):
    """The anchor that ANCHOR names cannot be built in this version."""


def _anchor_secret() -> bytes:
    """The signing key, read on every call and never kept, logged, or put in a message."""
    secret = os.environ.get(ANCHOR_SECRET_VAR) or None
    if secret is None:
        if os.environ.get("LIFELINE_ENV") == "production":
            raise RuntimeError(f"{ANCHOR_SECRET_VAR} must be set when LIFELINE_ENV is production.")
        secret = DEVELOPMENT_ANCHOR_SECRET
    return secret.encode("utf-8")


def _signed(head_hash: str, seq: int, user_hash: str, anchored_at: str) -> bytes:
    return json.dumps([head_hash, seq, user_hash, anchored_at], separators=(",", ":")).encode("utf-8")


def _signature(head_hash: str, seq: int, user_hash: str, anchored_at: str) -> str:
    return hmac.new(_anchor_secret(), _signed(head_hash, seq, user_hash, anchored_at), hashlib.sha256).hexdigest()


def _is_seq(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LocalSignedAnchor(Anchor):
    """Anchors a ledger head by appending a signed line to a file outside the ledger.

    A line holds only the head hash, its sequence number, a hash of the user id, a UTC time, and an
    HMAC over those four under LIFELINE_ANCHOR_SECRET, so nothing about money is ever written.
    """

    kind = LOCAL

    def __init__(self, path: Path, clock: Callable[[], datetime] = _now) -> None:
        self.path = path
        self._clock = clock

    def anchor(self, head_hash: str, seq: int, user_hash: str) -> str:
        if not isinstance(head_hash, str) or not DIGEST.fullmatch(head_hash):
            raise ValueError("An anchor takes a ledger head hash, 64 lowercase hexadecimal characters.")
        if not _is_seq(seq):
            raise ValueError("An anchor takes the head's sequence number, a whole number from zero.")
        if not isinstance(user_hash, str) or not DIGEST.fullmatch(user_hash):
            raise ValueError("An anchor takes a SHA 256 hash of the user id, never the id itself.")
        anchored_at = self._clock().astimezone(timezone.utc).isoformat()
        signature = _signature(head_hash, seq, user_hash, anchored_at)
        line = {"head_hash": head_hash, "seq": seq, "user_hash": user_hash, "anchored_at": anchored_at, "signature": signature}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
        return f"{LOCAL}:{signature[:32]}"

    def verify(self, head_hash: str) -> bool:
        return self._record(head_hash) is not None

    def anchored_at(self, head_hash: str) -> datetime | None:
        """The time recorded for the latest signed line of this head, or None when none checks."""
        record = self._record(head_hash)
        return None if record is None else datetime.fromisoformat(record["anchored_at"])

    def _record(self, head_hash: str) -> dict[str, Any] | None:
        found = None
        for record in self._records():
            if record["head_hash"] == head_hash and self._signed_by_us(record):
                found = record
        return found

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:  # anti-pattern: SILENT-EXCEPT ok, a line that is not JSON anchors nothing
                    continue
                if isinstance(record, dict) and set(record) == set(LINE_FIELDS):
                    records.append(record)
        return records

    @staticmethod
    def _signed_by_us(record: dict[str, Any]) -> bool:
        head_hash, seq, user_hash = record["head_hash"], record["seq"], record["user_hash"]
        anchored_at, signature = record["anchored_at"], record["signature"]
        if not all(isinstance(value, str) for value in (head_hash, user_hash, anchored_at, signature)) or not _is_seq(seq):
            return False
        expected = _signature(head_hash, seq, user_hash, anchored_at)
        return hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8"))


def anchor_for(env: Mapping[str, str] | None, path: Path) -> Anchor:
    """The anchor ANCHOR names: the local signed anchor at `path` for local or empty.

    FISCO BCOS arrives in a later change, so until then it is refused rather than quietly replaced.
    """
    kind = environment(env).get("ANCHOR", "").strip().casefold() or LOCAL
    if kind == LOCAL:
        return LocalSignedAnchor(path)
    if kind == FISCO:
        raise AnchorNotConfigured(
            "ANCHOR is fisco, and the FISCO BCOS anchor is not configured in this version. Set ANCHOR to local."
        )
    raise ValueError(f"ANCHOR must be one of {', '.join(ANCHOR_KINDS)}, not {kind!r}.")
