import json

import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import create_app
from contracts.schemas import Message, Role, ToolCall
from core.anchor_local import ANCHOR_SECRET_VAR, AnchorNotConfigured
from core.fake_adapter import FakeModelAdapter

USER = "student_001"
SECRET = "anchor-api-secret-0123456789"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
RENT_REQUEST = "Send 1,200 SGD rent to landlord_sp in Brazil"


@pytest.fixture(autouse=True)
def ledger_file(tmp_path, monkeypatch):
    path = tmp_path / "data" / "ledger.jsonl"
    monkeypatch.setattr(api.main, "LEDGER_PATH", path)
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")
    monkeypatch.setenv("ANCHOR", "")
    monkeypatch.setenv(ANCHOR_SECRET_VAR, SECRET)
    monkeypatch.delenv("LIFELINE_ENV", raising=False)
    return path


def _call(name: str, arguments: dict) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="",
        tool_calls=[ToolCall(id="toolu_01", name=name, arguments=arguments)],
        provider="fake",
        model="fake-model",
    )


def _client(responses=()) -> TestClient:
    return TestClient(create_app(adapter=FakeModelAdapter(list(responses)), tick_seconds=None))


def _pay_rent(client: TestClient) -> list[str]:
    proposed = client.post("/chat", json={"user_id": USER, "text": RENT_REQUEST})
    token = proposed.json()["confirmation"]["confirmation_token"]
    paid = client.post("/confirm", json={"user_id": USER, "confirmation_token": token})
    assert paid.json()["receipt"] is not None
    return [proposed.text, paid.text]


def test_verify_says_when_no_anchor_exists():
    body = _client().get(f"/ledger/{USER}/verify").json()

    assert (body["first_broken_seq"], body["anchor"], body["integrity_hold"]) == (None, {"anchored": False, "kind": "local"}, None)


def test_verify_shows_the_latest_anchor_and_that_it_verifies(ledger_file):
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)

    body = client.get(f"/ledger/{USER}/verify").json()

    entries = [json.loads(line) for line in ledger_file.read_text(encoding="utf-8").splitlines()]
    anchored = [entry for entry in entries if entry["kind"] == "anchor"][-1]
    assert body["first_broken_seq"] is None
    assert body["anchor"]["anchored"] is True
    assert body["anchor"]["head_hash"] == anchored["payload"]["head_hash"] == entries[anchored["seq"] - 2]["hash"]
    assert body["anchor"]["head_seq"] == anchored["seq"] - 1
    assert body["anchor"]["verified"] is True
    # The time shown is the one the anchor store recorded and signed.
    [line] = [json.loads(line) for line in (ledger_file.parent / "anchors.jsonl").read_text(encoding="utf-8").splitlines()]
    assert body["anchor"]["anchored_at"] == line["anchored_at"]
    assert body["anchor"]["kind"] == "local"


def test_a_tampered_anchor_line_verifies_false(ledger_file):
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)
    anchors = ledger_file.parent / "anchors.jsonl"
    line = json.loads(anchors.read_text(encoding="utf-8"))
    anchors.write_text(json.dumps({**line, "seq": line["seq"] + 1}) + "\n", encoding="utf-8")

    body = client.get(f"/ledger/{USER}/verify").json()

    assert body["anchor"]["anchored"] is True
    assert body["anchor"]["verified"] is False
    assert body["anchor"]["anchored_at"] is None


def test_the_secret_never_appears_in_a_response_an_entry_or_an_anchor_line(ledger_file):
    client = _client([_call("propose_transfer", RENT)])
    texts = _pay_rent(client)
    texts.append(client.get(f"/ledger/{USER}").text)
    texts.append(client.get(f"/ledger/{USER}/verify").text)
    texts.append(ledger_file.read_text(encoding="utf-8"))
    texts.append((ledger_file.parent / "anchors.jsonl").read_text(encoding="utf-8"))

    for text in texts:
        assert SECRET not in text


def test_an_anchor_store_that_fails_names_its_error_without_the_secret_and_the_payment_goes_through(ledger_file):
    # A directory where the anchor file should be makes every anchor write fail.
    (ledger_file.parent / "anchors.jsonl").mkdir(parents=True)
    client = _client([_call("propose_transfer", RENT)])

    texts = _pay_rent(client)

    entries = [json.loads(line) for line in ledger_file.read_text(encoding="utf-8").splitlines()]
    notes = [entry for entry in entries if entry["payload"].get("kind") == "anchor_failed"]
    assert len(notes) == 1
    assert "anchors.jsonl" in notes[0]["payload"]["error"]
    verify = client.get(f"/ledger/{USER}/verify")
    assert verify.status_code == 200
    assert verify.json()["anchor"] == {"anchored": False, "kind": "local"}
    for text in [*texts, verify.text, ledger_file.read_text(encoding="utf-8")]:
        assert SECRET not in text


@pytest.mark.parametrize("rpc_url", ["", "http://127.0.0.1:9"])
def test_anchor_fisco_unconfigured_or_unreachable_never_blocks_a_payment(monkeypatch, ledger_file, rpc_url):
    import time

    monkeypatch.setenv("ANCHOR", "fisco")
    monkeypatch.setenv("FISCO_RPC_URL", rpc_url)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", str(ledger_file.parent / "absent.key"))
    client = _client([_call("propose_transfer", RENT)])

    started = time.monotonic()
    _, paid = _pay_rent(client)

    assert time.monotonic() - started < 10
    assert json.loads(paid)["receipt"]["status"] == "completed"
    entries = [json.loads(line) for line in ledger_file.read_text(encoding="utf-8").splitlines()]
    notes = [entry["payload"] for entry in entries if entry["payload"].get("kind") == "anchor_failed"]
    assert len(notes) == 1
    assert "anchor" not in [entry["kind"] for entry in entries]
    assert client.get(f"/ledger/{USER}/verify").json()["anchor"] == {"anchored": False, "kind": "fisco"}


def test_the_students_ledger_lists_the_anchor_entry_after_a_t2_execution_and_the_anchors_file_holds_no_user_id(ledger_file):
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)

    listed = client.get(f"/ledger/{USER}").json()

    kinds = [entry["kind"] for entry in listed]
    assert kinds[-1] == "anchor"
    assert kinds.index("receipt") < kinds.index("anchor")
    assert listed[-1]["payload"]["user_id"] == USER
    anchors = (ledger_file.parent / "anchors.jsonl").read_text(encoding="utf-8")
    assert anchors.strip()
    assert USER not in anchors
