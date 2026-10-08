"""T18: the parent as a user. A rupee mandate from fixtures/demo_parent.yaml, run through the harness as
fixtures.user and loaded by the API beside the demo student; the cap enforced by the rail at execution
and named in the reply when it refuses."""

from decimal import Decimal
from pathlib import Path

import yaml

from api.main import DEMO_PARENT
from contracts.schemas import Mandate, Plan
from core.harness import evaluate, load_suite, run_scenario_run
from rails.knowledge.loader import load_knowledge
from rails.sim.rules import UPI_CAP_ENTRY, UPI_PURPOSE_ENTRY

PARENT = yaml.safe_load(DEMO_PARENT.read_text(encoding="utf-8"))
SEND = {"amount": "40000", "currency": "INR", "corridor": "IN>SG", "payee_id": "student_001", "purpose": "gift"}


def test_the_parent_fixture_is_marked_and_valid():
    text = DEMO_PARENT.read_text(encoding="utf-8")
    assert "Not a real person" in text and "Source: this file." in text
    Plan.model_validate(PARENT["plan"])
    Mandate.model_validate({"user_id": PARENT["user_id"], "valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-01-01T00:00:00Z", **PARENT["mandate"]})


def test_the_parent_sends_only_to_the_student_on_in_sg_for_the_rbis_purposes():
    mandate = PARENT["mandate"]
    entries = load_knowledge()

    assert mandate["currency"] == "INR"
    assert mandate["allowed_payees"] == ["student_001"]
    assert mandate["allowed_corridors"] == ["IN>SG"]
    assert mandate["allowed_purposes"] == entries[UPI_PURPOSE_ENTRY]["values"]["purposes"]
    assert Decimal(mandate["per_txn_limit"]) < Decimal(str(entries[UPI_CAP_ENTRY]["values"]["daily_cap"]))


def _scenario(turns, expected):
    return {"id": "T18", "fixtures": {"user": {"fixture": "demo_parent"}}, "runs": [{"lang": "en", "turns": turns, "expected": expected}]}


def _propose(amount):
    return [
        {"user": f"Send {amount} rupees to student_001 as a gift", "model": [{"calls": [{"name": "propose_transfer", "arguments": {**SEND, "amount": amount}}]}]},
        {"user": "Yes", "confirm": "latest"},
    ]


def test_a_scenario_runs_as_the_parent_named_by_fixtures_user():
    scenario = _scenario(_propose("40000"), {"reply": "receipt", "ledger": ["proposal", "decision", "confirmation", "execution", "receipt"], "must_contain": ["This was a simulation"]})

    assert run_scenario_run(scenario, scenario["runs"][0]).failures == []


def test_a_user_block_can_be_written_inline():
    block = {"user_id": "parent_002", **{key: PARENT[key] for key in ("mandate", "balances", "plan")}}
    block["mandate"] = {**block["mandate"], "id": "mandate-parent_002-v1"}
    scenario = {"id": "T18", "fixtures": {"user": block}, "runs": [{"lang": "en", "turns": _propose("40000"), "expected": {"reply": "receipt"}}]}

    assert run_scenario_run(scenario, scenario["runs"][0]).failures == []


def test_the_parent_cannot_pay_the_landlord_of_the_demo_student():
    turns = [{"user": "Send 40000 rupees to landlord_sp", "model": [{"calls": [{"name": "propose_transfer", "arguments": {**SEND, "payee_id": "landlord_sp"}}]}]}]
    scenario = _scenario(turns, {"reply": "refusal", "rule_ids": ["R06"]})

    assert run_scenario_run(scenario, scenario["runs"][0]).failures == []


def test_a_second_transfer_the_same_day_over_the_cap_is_refused_by_the_rail_and_the_reply_names_the_cap():
    turns = _propose("40000") + _propose("30000")
    expected = {
        "reply": "answer",
        "ledger": ["proposal", "decision", "confirmation", "execution", "receipt", "proposal", "decision", "confirmation", "note"],
        "must_contain": [UPI_CAP_ENTRY, "nothing was sent"],
    }
    scenario = _scenario(turns, expected)

    assert run_scenario_run(scenario, scenario["runs"][0]).failures == []


def test_without_fixtures_user_the_demo_student_is_still_the_user():
    scenario = load_suite(Path(__file__).resolve().parent.parent / "suites" / "scenarios" / "T06.yaml")

    assert all(run.passed for run in [run_scenario_run(scenario, run) for run in scenario["runs"]])


def test_every_existing_scenario_still_passes():
    assert [result.id for result in evaluate() if result.status == "failed"] == []


def test_the_ledger_shows_the_whole_truth_of_the_refused_second_transfer():
    from contracts.schemas import Message, Role
    from core.agent import AgentLoop
    from core.fake_adapter import FakeModelAdapter
    from core.harness import _who
    from core.ledger import HashChainLedger
    from core.mandate import DeterministicMandateEngine
    from rails.fake_router import FakeRouter
    from rails.sim.upi_paynow import UpiPayNowSimRail
    from tests.test_agent import _call

    who = _who({"user": {"fixture": "demo_parent"}})
    ledger = HashChainLedger()
    loop = AgentLoop(
        adapter=FakeModelAdapter([_call("propose_transfer", SEND), _call("propose_transfer", {**SEND, "amount": "30000"})]),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails={"upi_paynow_sim": UpiPayNowSimRail()},
        mandates={who.user_id: who.mandate},
        balances={who.user_id: who.balances},
        pending={},
        plans={who.user_id: who.plan},
    )
    for amount in ("40000", "30000"):
        token = loop.handle(who.user_id, Message(role=Role.USER, text=f"Send {amount} rupees to student_001 as a gift")).confirmation.confirmation_token
        reply = loop.handle(who.user_id, Message(role=Role.USER, text="Yes"), confirmation_token=token)

    second = [e for e in ledger.entries() if e.kind != "turn"][-4:]
    assert [e.kind for e in second] == ["proposal", "decision", "confirmation", "note"]
    assert UPI_CAP_ENTRY in second[-1].payload["rail_error"]
    assert second[-1].payload["executed"] is False
    assert [e.kind for e in ledger.entries()].count("receipt") == 1
    assert reply.receipt is None and UPI_CAP_ENTRY in reply.text
