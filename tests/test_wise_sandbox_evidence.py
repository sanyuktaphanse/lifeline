"""The Wise sandbox evidence run pays through the API, the engine and the ledger, never around them."""

import json

import httpx
import pytest

from rails.wise_sandbox import WiseSandboxClient, WiseSandboxConfig
from rails.wise_sandbox_evidence import main, run
from tests.test_wise_sandbox import PROFILE, RECIPIENTS, SCA_SENTENCE, TOKEN, FakeWise


def _client(wise):
    config = WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients=dict(RECIPIENTS))
    return WiseSandboxClient(config, transport=httpx.MockTransport(wise.handler))


def _ledger_kinds(workdir):
    lines = (workdir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["kind"] for line in lines]


def test_every_payment_goes_through_a_proposal_a_decision_and_a_confirmation(tmp_path):
    wise = FakeWise()

    run(_client(wise), tmp_path / "wise-sandbox.md", tmp_path / "run")

    kinds = _ledger_kinds(tmp_path / "run")
    payments = kinds.count("receipt")
    assert payments == 2
    assert kinds.count("proposal") >= 3
    assert kinds.count("confirmation") == 3
    # Every receipt follows its execution, and every execution its confirmation.
    for index, kind in enumerate(kinds):
        if kind == "receipt":
            assert "execution" in kinds[:index] and "confirmation" in kinds[:index]
    assert len(wise.transfers) == 2


def test_the_log_shows_each_step_the_ledger_verifies_and_no_token_appears(tmp_path):
    out = tmp_path / "wise-sandbox.md"

    run(_client(FakeWise()), out, tmp_path / "run")

    log = out.read_text(encoding="utf-8")
    assert "Wise sandbox operation log" in log
    for step in ("propose", "confirm", "trace", "simulate", "cancel", "verify"):
        assert f"| {step} |" in log
    assert "outgoing_payment_sent" in log
    assert "simulated True" in log
    assert "first broken entry: none" in log
    assert "No real money moves" in log
    assert TOKEN not in log
    assert "confirmation_token" not in log


def test_the_run_refuses_to_start_without_a_token(tmp_path, monkeypatch):
    monkeypatch.setenv("WISE_SANDBOX_TOKEN", "")

    with pytest.raises(SystemExit, match="WISE_SANDBOX_TOKEN"):
        main(["--out", str(tmp_path / "x.md")])


def test_the_run_refuses_when_the_demo_payee_has_no_sandbox_recipient(tmp_path):
    config = WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients={"landlord_sp": 1})
    client = WiseSandboxClient(config, transport=httpx.MockTransport(FakeWise().handler))

    with pytest.raises(SystemExit, match="WISE_SANDBOX_RECIPIENTS"):
        run(client, tmp_path / "x.md", tmp_path / "run")


def test_a_refused_funding_is_logged_in_full_with_the_balance_that_was_held(tmp_path):
    out = tmp_path / "wise-sandbox.md"
    balances = [{"id": 1, "currency": "SGD", "type": "STANDARD", "visible": True, "amount": {"value": 1000, "currency": "SGD"}}]
    wise = FakeWise(fund_code=403, fund_sca=True, balances=balances)

    run(_client(wise), out, tmp_path / "run")

    log = out.read_text(encoding="utf-8")
    refused = [line for line in log.splitlines() if line.startswith("| ") and "| confirm |" in line and "no receipt" in line]
    assert len(refused) == 2
    for line in refused:
        assert "and refused to fund it: " + SCA_SENTENCE in line
    balance = [line for line in log.splitlines() if "| balance |" in line]
    assert len(balance) == 1
    assert "sandbox only" in balance[0] and "SGD balance held: 1000" in balance[0]
    assert "receipt" not in _ledger_kinds(tmp_path / "run")
    assert "first broken entry: none" in log
    assert TOKEN not in log
    assert "confirmation_token" not in log
    assert "made-up-approval-id" not in log
    assert all(transfer["status"] == "cancelled" for transfer in wise.transfers.values())
