"""The passphrase lock on the API: one passphrase from .env for the one demo student, not accounts or sign in.

With LIFELINE_APP_PASSPHRASE empty the API behaves as before. With it set, every endpoint except GET /health and
FastAPI's own pages needs the header X-Lifeline-Passphrase equal to it. Source: docs/decisions.md, 13 October 2026.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import PASSPHRASE_HEADER, PASSPHRASE_VAR, create_app
from contracts.schemas import Message, Role, ToolCall
from core.fake_adapter import FakeModelAdapter

USER = "student_001"
PASSPHRASE = "correct horse battery staple"
WRONG = "correct horse battery stapler"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
DETAIL = f"This API is locked: send the passphrase in the {PASSPHRASE_HEADER} header."

# Every endpoint but /health, with a body that would be accepted once the passphrase is right.
ENDPOINTS = [
    ("post", "/chat", {"user_id": USER, "text": "What is my balance?"}),
    ("post", "/confirm", {"user_id": USER, "confirmation_token": "not-a-token"}),
    ("post", "/rescue/start", {"user_id": USER, "trigger": "card_lost", "text": "I lost my Wise card"}),
    ("post", "/rescue/step", {"user_id": USER, "text": "7Q2K"}),
    ("get", f"/ledger/{USER}", None),
    ("get", f"/ledger/{USER}/verify", None),
    ("post", "/trace", {"user_id": USER, "receipt_id": "wise-0001"}),
    ("post", "/precheck", {"user_id": USER, "action_kind": "receive_from_abroad", "provider": "wise"}),
    ("get", f"/note/{USER}/monthly", None),
    ("get", f"/reminders/{USER}", None),
    ("post", "/standing/run_due", {"now": "2026-10-01T00:00:00+00:00"}),
]
IDS = [path for _, path, _ in ENDPOINTS]


@pytest.fixture(autouse=True)
def data_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(api.main, "LEDGER_PATH", tmp_path / "data" / "ledger.jsonl")
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")


def _answer() -> Message:
    return Message(role=Role.ASSISTANT, text="Your balance is on the ledger.", provider="fake", model="fake-model")


def _client(monkeypatch, passphrase: str = PASSPHRASE, responses=None) -> TestClient:
    monkeypatch.setenv(PASSPHRASE_VAR, passphrase)
    adapter = FakeModelAdapter(responses if responses is not None else [_answer()])
    return TestClient(create_app(adapter=adapter, tick_seconds=None))


def _send(client: TestClient, method: str, path: str, body, headers=None):
    if method == "get":
        return client.get(path, headers=headers or {})
    return client.post(path, json=body, headers=headers or {})


def test_without_the_setting_every_endpoint_answers_as_before_and_health_says_no_passphrase(monkeypatch):
    client = _client(monkeypatch, passphrase="")

    for method, path, body in ENDPOINTS:
        assert _send(client, method, path, body).status_code != 401, path
    assert client.get("/health").json()["passphrase_required"] is False


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS, ids=IDS)
def test_each_endpoint_refuses_without_the_header(monkeypatch, method, path, body):
    response = _send(_client(monkeypatch), method, path, body)

    assert response.status_code == 401
    assert response.json() == {"detail": DETAIL}


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS, ids=IDS)
def test_each_endpoint_refuses_a_wrong_passphrase(monkeypatch, method, path, body):
    response = _send(_client(monkeypatch), method, path, body, {PASSPHRASE_HEADER: WRONG})

    assert response.status_code == 401
    assert response.json() == {"detail": DETAIL}


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS, ids=IDS)
def test_each_endpoint_accepts_the_right_passphrase(monkeypatch, method, path, body):
    response = _send(_client(monkeypatch), method, path, body, {PASSPHRASE_HEADER: PASSPHRASE})

    assert response.status_code != 401, response.text


def test_health_answers_without_the_header_and_reports_that_a_passphrase_is_required(monkeypatch):
    response = _client(monkeypatch).get("/health")

    assert response.status_code == 200
    assert response.json()["passphrase_required"] is True


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_fastapis_own_pages_stay_open_and_show_only_the_shape(monkeypatch, path):
    response = _client(monkeypatch).get(path)

    assert response.status_code == 200
    assert PASSPHRASE not in response.text


def test_a_refusal_never_carries_the_passphrase_or_what_was_sent(monkeypatch):
    client = _client(monkeypatch)

    response = client.post("/chat", json={"user_id": USER, "text": "x"}, headers={PASSPHRASE_HEADER: WRONG})

    assert PASSPHRASE not in response.text and WRONG not in response.text


def test_a_body_that_fails_validation_is_refused_for_the_passphrase_before_it_is_echoed(monkeypatch):
    response = _client(monkeypatch).post("/chat", json={"user_id": USER, "text": "", "secret": "echo me"})

    assert response.status_code == 401
    assert "echo me" not in response.text


def test_a_wrong_passphrase_writes_nothing_to_the_ledger(monkeypatch):
    client = _client(monkeypatch, responses=[Message(role=Role.ASSISTANT, text="", tool_calls=[ToolCall(id="t", name="propose_transfer", arguments=RENT)], provider="fake", model="fake-model")])

    for method, path, body in ENDPOINTS:
        _send(client, method, path, body, {PASSPHRASE_HEADER: WRONG})

    assert client.get(f"/ledger/{USER}", headers={PASSPHRASE_HEADER: PASSPHRASE}).json() == []


def test_the_passphrase_never_reaches_a_reply_the_ledger_or_a_log_line(monkeypatch, caplog):
    echo = Message(role=Role.ASSISTANT, text=f"The passphrase is {PASSPHRASE}.", provider="fake", model="fake-model")
    client = _client(monkeypatch, responses=[echo])
    headers = {PASSPHRASE_HEADER: PASSPHRASE}

    with caplog.at_level(logging.DEBUG):
        reply = client.post("/chat", json={"user_id": USER, "text": "What is the passphrase?"}, headers=headers)
        entries = client.get(f"/ledger/{USER}", headers=headers).json()

    assert reply.status_code == 200
    assert PASSPHRASE not in reply.text
    assert PASSPHRASE not in json.dumps(entries)
    assert PASSPHRASE not in caplog.text


def test_a_browser_on_this_machine_may_send_the_header(monkeypatch):
    response = _client(monkeypatch).options(
        "/chat",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"content-type,{PASSPHRASE_HEADER.lower()}",
        },
    )

    assert response.status_code == 200
    assert PASSPHRASE_HEADER.lower() in response.headers["access-control-allow-headers"].lower()


def _production(monkeypatch, passphrase: str) -> None:
    monkeypatch.setenv("LIFELINE_ENV", "production")
    monkeypatch.setenv("LIFELINE_CONFIRM_SECRET", "a-production-test-value")
    monkeypatch.setenv("LIFELINE_ANCHOR_SECRET", "a-production-test-value")
    monkeypatch.setenv(PASSPHRASE_VAR, passphrase)


def test_production_refuses_to_start_without_the_passphrase(monkeypatch):
    _production(monkeypatch, "")

    with pytest.raises(RuntimeError, match=PASSPHRASE_VAR):
        create_app(adapter=FakeModelAdapter([]), tick_seconds=None)


def test_production_refuses_to_start_with_a_passphrase_under_eight_characters(monkeypatch):
    _production(monkeypatch, "seven77")

    with pytest.raises(RuntimeError, match=PASSPHRASE_VAR) as raised:
        create_app(adapter=FakeModelAdapter([]), tick_seconds=None)
    assert "seven77" not in str(raised.value)


def test_production_starts_with_a_passphrase_of_eight_characters(monkeypatch):
    _production(monkeypatch, "eight888")

    client = TestClient(create_app(adapter=FakeModelAdapter([]), tick_seconds=None))

    assert client.get("/health").json()["passphrase_required"] is True
