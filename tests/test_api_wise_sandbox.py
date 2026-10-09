"""The API uses the Wise sandbox only when it is given one or WISE_SANDBOX_TOKEN is set, and keeps its fixture otherwise."""

import httpx
import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import create_app, wise_sandbox_client
from core.fake_adapter import FakeModelAdapter
from rails.fake_rail import FakeRail
from rails.fake_router import FakeRouter
from rails.wise_sandbox import WiseSandboxClient, WiseSandboxConfig, WiseSandboxRail, WiseSandboxRouter
from tests.test_api import USER, _call
from tests.test_wise_sandbox import PROFILE, RECIPIENTS, TOKEN, FakeWise

ALLOWANCE = {"amount": "300", "currency": "SGD", "corridor": "SG>SG", "payee_id": "self_sg", "purpose": "emergency"}


@pytest.fixture(autouse=True)
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(api.main, "LEDGER_PATH", tmp_path / "data" / "ledger.jsonl")
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")


def _sandbox(wise):
    config = WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients=dict(RECIPIENTS))
    return WiseSandboxClient(config, transport=httpx.MockTransport(wise.handler))


def test_without_a_token_the_api_keeps_the_fixture_wise_rail_and_router():
    loop = create_app(adapter=FakeModelAdapter([]), tick_seconds=None).state.loop

    assert isinstance(loop._rails["wise"], FakeRail)
    assert type(loop._router) is FakeRouter


def test_a_token_in_the_environment_builds_the_sandbox_client():
    env = {"WISE_SANDBOX_TOKEN": TOKEN, "WISE_SANDBOX_PROFILE_ID": "101", "WISE_SANDBOX_RECIPIENTS": "self_sg:555"}

    assert isinstance(wise_sandbox_client(env), WiseSandboxClient)
    assert wise_sandbox_client({"WISE_SANDBOX_TOKEN": ""}) is None


def test_with_a_sandbox_the_wise_rail_and_its_quotes_come_from_it():
    loop = create_app(adapter=FakeModelAdapter([]), tick_seconds=None, wise_sandbox=_sandbox(FakeWise())).state.loop

    assert isinstance(loop._rails["wise"], WiseSandboxRail)
    assert isinstance(loop._router, WiseSandboxRouter)
    assert isinstance(loop._rails["bank_wire"], FakeRail)


def test_an_allowance_to_the_students_own_account_is_paid_on_the_sandbox_and_says_simulated():
    wise = FakeWise(fee="0.42")
    client = TestClient(
        create_app(adapter=FakeModelAdapter([_call("propose_transfer", ALLOWANCE)]), tick_seconds=None, wise_sandbox=_sandbox(wise))
    )

    proposed = client.post("/chat", json={"user_id": USER, "text": "Send 300 SGD to my own account, emergency"}).json()
    route = proposed["confirmation"]["selected_route"]
    confirmed = client.post(
        "/confirm", json={"user_id": USER, "confirmation_token": proposed["confirmation"]["confirmation_token"]}
    ).json()

    assert (route["rail"], route["fee"], route["simulated"]) == ("wise", "0.42", True)
    assert confirmed["receipt"]["rail"] == "wise"
    assert confirmed["receipt"]["simulated"] is True
    assert confirmed["receipt"]["receipt_id"] == "wise-16521632"
    assert len(wise.transfers) == 1
