"""The breaks the anchor attacker brief of 8 October found, each as a test that failed before its fix."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import create_app
from contracts.schemas import LedgerEntry, Message, Role, ToolCall
from core.anchor_local import ANCHOR_SECRET_VAR, DEVELOPMENT_ANCHOR_SECRET, LocalSignedAnchor
from core.fake_adapter import FakeModelAdapter
from core.ledger import GENESIS_PREV_HASH, _hash_of

USER = "student_001"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
SMALL = {**RENT, "amount": "50"}


@pytest.fixture(autouse=True)
def ledger_file(tmp_path, monkeypatch):
    path = tmp_path / "data" / "ledger.jsonl"
    monkeypatch.setattr(api.main, "LEDGER_PATH", path)
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")
    monkeypatch.setenv("ANCHOR", "")
    monkeypatch.setenv(ANCHOR_SECRET_VAR, "anchor-attack-secret-0123456789")
    monkeypatch.delenv("LIFELINE_ENV", raising=False)
    return path


def _call(arguments: dict) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="",
        tool_calls=[ToolCall(id="toolu_01", name="propose_transfer", arguments=arguments)],
        provider="fake",
        model="fake-model",
    )


def _client(responses=(), ledger_path: Path | None = None) -> TestClient:
    return TestClient(
        create_app(adapter=FakeModelAdapter(list(responses)), tick_seconds=None, ledger_path=ledger_path)
    )


def _pay(client: TestClient, text: str = "Send 1,200 SGD rent to landlord_sp") -> None:
    token = client.post("/chat", json={"user_id": USER, "text": text}).json()["confirmation"]["confirmation_token"]
    assert client.post("/confirm", json={"user_id": USER, "confirmation_token": token}).json()["receipt"]


def _entries(path: Path) -> list[LedgerEntry]:
    return [LedgerEntry.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rechain(path: Path, entries: list[LedgerEntry]) -> None:
    """Rewrite the file as a forger would: every hash recomputed, so the chain itself verifies."""
    prev = GENESIS_PREV_HASH
    for seq, entry in enumerate(entries, start=1):
        entry.seq, entry.prev_hash = seq, prev
        entry.hash = _hash_of(entry)
        prev = entry.hash
    path.write_text("".join(entry.model_dump_json() + "\n" for entry in entries), encoding="utf-8")


def _edit_amounts(entries: list[LedgerEntry], old: str, new: str) -> list[LedgerEntry]:
    return [LedgerEntry.model_validate_json(entry.model_dump_json().replace(f'"{old}"', f'"{new}"')) for entry in entries]


def _status() -> dict:
    body = _client().get(f"/ledger/{USER}/verify").json()
    assert body["first_broken_seq"] is None
    return body["anchor"]


def test_an_edited_and_rechained_ledger_does_not_verify_against_its_anchor(ledger_file):
    _pay(_client([_call(RENT)]))
    _rechain(ledger_file, _edit_amounts(_entries(ledger_file), "1200", "9999"))

    status = _status()

    assert status["anchored"] is True
    assert status["matches_ledger"] is False
    assert status["verified"] is False


def test_an_anchor_entry_pointed_at_an_older_signed_head_does_not_verify(ledger_file):
    client = _client([_call(RENT), _call(SMALL)])
    _pay(client)
    _pay(client, "Send 50 SGD rent to landlord_sp")
    entries = _entries(ledger_file)
    first, last = [entry for entry in entries if entry.kind == "anchor"]
    last.payload["head_hash"], last.payload["head_seq"] = first.payload["head_hash"], first.payload["head_seq"]
    _rechain(ledger_file, _edit_amounts(entries, "50", "5000"))

    assert _status()["verified"] is False


def test_a_line_replayed_from_another_ledger_does_not_verify(ledger_file, tmp_path):
    other = tmp_path / "other" / "ledger.jsonl"
    _pay(_client([_call(SMALL)], ledger_path=other), "Send 50 SGD rent to landlord_sp")
    _pay(_client([_call(RENT)]))
    foreign = json.loads((other.parent / "anchors.jsonl").read_text(encoding="utf-8"))
    anchors = ledger_file.parent / "anchors.jsonl"
    anchors.write_text(anchors.read_text(encoding="utf-8") + json.dumps(foreign) + "\n", encoding="utf-8")
    entries = _edit_amounts(_entries(ledger_file), "1200", "9999")
    anchor_entry = [entry for entry in entries if entry.kind == "anchor"][-1]
    anchor_entry.payload["head_hash"] = foreign["head_hash"]

    _rechain(ledger_file, entries)

    assert _status()["verified"] is False


def test_a_ledger_truncated_after_its_first_anchor_does_not_verify(ledger_file):
    client = _client([_call(RENT), _call(SMALL)])
    _pay(client)
    _pay(client, "Send 50 SGD rent to landlord_sp")
    entries = _entries(ledger_file)
    first = next(entry for entry in entries if entry.kind == "anchor")
    ledger_file.write_text("".join(entry.model_dump_json() + "\n" for entry in entries[: first.seq]), encoding="utf-8")

    status = _status()

    assert status["anchored"] is True
    assert status["verified"] is False


def test_a_tampered_ledger_is_never_anchored_so_a_later_payment_cannot_launder_it(ledger_file):
    _pay(_client([_call(RENT)]))
    _rechain(ledger_file, _edit_amounts(_entries(ledger_file), "1200", "1100"))
    anchors = ledger_file.parent / "anchors.jsonl"
    lines_before = anchors.read_text(encoding="utf-8")

    _pay(_client([_call(SMALL)]), "Send 50 SGD rent to landlord_sp")

    assert anchors.read_text(encoding="utf-8") == lines_before
    entries = _entries(ledger_file)
    skipped = [entry for entry in entries if entry.payload.get("kind") == "anchor_skipped"]
    assert len(skipped) == 1
    assert "does not match" in skipped[0].payload["reason"]
    assert _status()["verified"] is False


def test_a_broken_chain_is_never_anchored(ledger_file):
    _pay(_client([_call(RENT)]))
    text = ledger_file.read_text(encoding="utf-8")
    ledger_file.write_text(text.replace('"1200"', '"1100"', 1), encoding="utf-8")
    anchors = ledger_file.parent / "anchors.jsonl"
    lines_before = anchors.read_text(encoding="utf-8")

    _pay(_client([_call(SMALL)]), "Send 50 SGD rent to landlord_sp")

    assert anchors.read_text(encoding="utf-8") == lines_before
    reasons = [entry.payload["reason"] for entry in _entries(ledger_file) if entry.payload.get("kind") == "anchor_skipped"]
    assert reasons == ["The ledger chain breaks at entry 1, so its head is not anchored."]


def test_an_honest_ledger_with_several_anchors_still_verifies(ledger_file):
    client = _client([_call(RENT), _call(SMALL)])
    _pay(client)
    _pay(client, "Send 50 SGD rent to landlord_sp")

    status = _status()

    assert (status["verified"], status["matches_ledger"]) == (True, True)
    assert "development_secret" not in status


def test_the_status_says_when_the_public_development_secret_signs(ledger_file, monkeypatch):
    monkeypatch.setenv(ANCHOR_SECRET_VAR, "")
    _pay(_client([_call(RENT)]))

    status = _status()

    # Anyone can sign with the development secret, so a pass under it is marked as such.
    assert status["development_secret"] is True
    assert DEVELOPMENT_ANCHOR_SECRET not in json.dumps(status)
    assert LocalSignedAnchor(ledger_file.parent / "anchors.jsonl").uses_development_secret() is True
