"""The Wise sandbox evidence run writes an operation log from what the sandbox answered, and never the token."""

import httpx
import pytest

from rails.wise_sandbox import WiseSandboxClient, WiseSandboxConfig
from rails.wise_sandbox_evidence import main, run
from tests.test_wise_sandbox import PROFILE, RECIPIENTS, TOKEN, FakeWise


def _client(wise):
    config = WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients=dict(RECIPIENTS))
    return WiseSandboxClient(config, transport=httpx.MockTransport(wise.handler))


def test_the_run_pays_traces_and_cancels_and_logs_each_step(tmp_path):
    wise = FakeWise()
    out = tmp_path / "wise-sandbox.md"

    run(_client(wise), "self_sg", out)

    log = out.read_text(encoding="utf-8")
    assert "Wise sandbox operation log" in log
    for step in ("quote", "execute", "trace", "simulate", "cancel"):
        assert f"| {step} |" in log
    assert "outgoing_payment_sent" in log
    assert "completed" in log
    assert "No real money moves" in log
    assert TOKEN not in log
    assert len(wise.transfers) == 2


def test_the_run_refuses_to_start_without_a_token(tmp_path, monkeypatch):
    monkeypatch.setenv("WISE_SANDBOX_TOKEN", "")

    with pytest.raises(SystemExit, match="WISE_SANDBOX_TOKEN"):
        main(["--out", str(tmp_path / "x.md")])


def test_the_run_refuses_a_payee_with_no_sandbox_recipient(tmp_path):
    with pytest.raises(SystemExit, match="WISE_SANDBOX_RECIPIENTS"):
        run(_client(FakeWise()), "stranger", tmp_path / "x.md")
