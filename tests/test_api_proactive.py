"""Stage 9 over HTTP: the monthly note, and the reminders the app delivers."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import create_app
from contracts.schemas import Message, Role, ToolCall
from core.fake_adapter import FakeModelAdapter
from core.monthly import month_of, next_month, seqs_of

USER = "student_001"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
RENT_REQUEST = "Send 1,200 SGD rent to landlord_sp in Brazil"


@pytest.fixture(autouse=True)
def ledger_file(tmp_path, monkeypatch):
    path = tmp_path / "data" / "ledger.jsonl"
    monkeypatch.setattr(api.main, "LEDGER_PATH", path)
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")
    return path


def _call(name: str, arguments: dict) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="",
        tool_calls=[ToolCall(id="toolu_01", name=name, arguments=arguments)],
        provider="fake",
        model="fake-model",
    )


def _say(text: str) -> Message:
    return Message(role=Role.ASSISTANT, text=text, provider="fake", model="fake-model")


def _client(responses=()) -> TestClient:
    return TestClient(create_app(adapter=FakeModelAdapter(list(responses)), tick_seconds=None))


def _pay_rent(client: TestClient, lang: str | None = None) -> None:
    fields = {"lang": lang} if lang else {}
    token = client.post("/chat", json={"user_id": USER, "text": RENT_REQUEST, **fields}).json()["confirmation"][
        "confirmation_token"
    ]
    client.post("/confirm", json={"user_id": USER, "confirmation_token": token, **fields})


def _month() -> str:
    return month_of(datetime.now(timezone.utc))


def _first_of_next_month(month: str) -> datetime:
    return datetime.fromisoformat(f"{next_month(month)}-01T00:00:00+00:00")


# GET /note/{user}/monthly


def test_the_note_endpoint_returns_the_text_the_summary_and_the_sequences_for_the_month_given():
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)

    response = client.get(f"/note/{USER}/monthly", params={"month": _month()})

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == USER
    assert body["month"] == _month()
    assert body["lang"] == "en"
    assert "1 sent on SG>BR, total 1200 SGD, fees 5.60 SGD" in body["text"]
    assert body["seqs"] == seqs_of(body["summary"])
    execution = next(e for e in client.get(f"/ledger/{USER}").json() if e["kind"] == "execution")
    assert execution["seq"] in body["seqs"]


def test_without_a_month_the_note_is_for_the_latest_month_that_has_entries():
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)

    body = client.get(f"/note/{USER}/monthly").json()

    latest = client.get(f"/ledger/{USER}").json()[-1]
    assert body["month"] == month_of(datetime.fromisoformat(latest["ts"]))


def test_a_student_with_no_entries_gets_the_note_for_the_current_month():
    body = _client().get(f"/note/{USER}/monthly").json()

    assert body["month"] == _month()
    assert "no transfers were sent" in body["text"]
    assert body["seqs"] == []


def test_the_note_is_in_the_language_of_the_students_latest_turn():
    client = _client([_call("propose_transfer", RENT), _say("Olá")])
    _pay_rent(client)
    client.post("/chat", json={"user_id": USER, "text": "Olá, tudo bem?"})

    body = client.get(f"/note/{USER}/monthly", params={"month": _month()}).json()

    assert body["lang"] == "pt"
    assert "Nota do Lifeline para" in body["text"]


def test_the_note_for_an_unknown_student_is_404():
    assert _client().get("/note/nobody/monthly").status_code == 404


@pytest.mark.parametrize("month", ["2026-13", "26-10", "2026-1", "last month", "２０２６-１０", "2026-10-01", "<script>"])
def test_a_malformed_month_is_422_and_never_echoes_the_input(month):
    response = _client().get(f"/note/{USER}/monthly", params={"month": month})

    assert response.status_code == 422
    assert month not in response.text


def test_the_chat_tool_the_tick_and_the_endpoint_give_the_same_text():
    month = _month()
    client = _client([_call("propose_transfer", RENT), _call("monthly_summary", {}), _say("")])
    _pay_rent(client)
    reply = client.post("/chat", json={"user_id": USER, "text": "Give me this month's note"}).json()

    endpoint = client.get(f"/note/{USER}/monthly", params={"month": month}).json()
    client.post("/standing/run_due", json={"now": _first_of_next_month(month).isoformat()})
    tick = next(
        e["payload"] for e in client.get(f"/ledger/{USER}").json() if e["payload"].get("kind") == "monthly_note"
    )

    assert endpoint["text"] in reply["text"]
    assert tick["text"] == endpoint["text"]
    assert tick["seqs"] == endpoint["seqs"]


def _trail(client: TestClient) -> list[dict]:
    return [e for e in client.get(f"/ledger/{USER}").json() if e["kind"] not in ("turn", "anchor")]


def test_the_note_endpoint_runs_monthly_summary_as_a_t0_action_through_the_engine():
    client = _client([_call("propose_transfer", RENT)])
    _pay_rent(client)
    before = len(_trail(client))

    client.get(f"/note/{USER}/monthly", params={"month": _month()})

    added = _trail(client)[before:]
    assert [e["kind"] for e in added] == ["proposal", "decision", "execution"]
    assert added[1]["payload"]["decision"]["tier"] == "T0"
    assert added[2]["payload"]["action"]["type"] == "monthly_summary"


def test_a_malformed_month_writes_nothing():
    client = _client()

    client.get(f"/note/{USER}/monthly", params={"month": "2026-13"})

    assert _trail(client) == []
