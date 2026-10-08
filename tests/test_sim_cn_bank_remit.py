from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import Action, ActionType, Message, ReceiptStatus, Role
from core.agent import AgentLoop
from core.fake_adapter import FakeModelAdapter
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine, check
from rails.fake_router import FakeRouter
from rails.inbound import inbound_from_fixture, seed_inbound
from rails.knowledge.loader import load_knowledge
from rails.sim.base import SCAM_TEXT, SCRIPTS
from rails.sim.cn_bank_remit import CnBankRemitSimRail
from tests.test_agent import USER, _call, _mandate, _user

DOCUMENTS = load_knowledge()["cn_boc_anxin_009"]["values"]["documents"]
INBOUND_ID = "cn_bank_remit_sim-in-0001"


def _rail(script="normal", documents=DOCUMENTS, quota_known=True):
    return CnBankRemitSimRail(documents_on_file=documents, quota_position_known=quota_known, script=script)


def _route(purpose="living_costs"):
    route = FakeRouter().quote("CN>SG", Decimal("20000"), purpose, "normal")[0]
    return route.model_copy(update={"payee_id": "student_001_anxin"})


def _pay(rail, purpose="living_costs"):
    return rail.execute(_route(purpose), "mandate-parent-v1", "cn-key-0001", "token")


def test_the_rail_is_a_simulated_rail_named_cn_bank_remit_sim():
    rail = _rail()

    assert isinstance(rail, Rail)
    assert (rail.name, rail.simulated) == ("cn_bank_remit_sim", True)


def test_funding_the_student_with_the_checklist_complete_and_the_quota_known_is_paid():
    receipt = _pay(_rail())

    assert receipt.receipt_id == "cn_bank_remit_sim-0001"
    assert receipt.status is ReceiptStatus.CREATED
    assert receipt.simulated is True
    assert (receipt.amount, receipt.currency) == (Decimal("20000"), "CNY")


def test_paying_the_institution_is_refused_citing_nus_and_the_hsbc_entry():
    with pytest.raises(RailError) as refused:
        _pay(_rail(), purpose="tuition")

    assert "sg_nus_fee_payment_003" in str(refused.value)
    assert "cn_edu_remit_002" in str(refused.value)


def test_any_other_purpose_is_refused_with_no_sourced_rule():
    with pytest.raises(RailError, match="no sourced rule"):
        _pay(_rail(), purpose="rent")


@pytest.mark.parametrize("missing", DOCUMENTS)
def test_a_missing_document_is_refused_naming_it_and_the_entry(missing):
    held = [document for document in DOCUMENTS if document != missing]

    with pytest.raises(RailError) as refused:
        _pay(_rail(documents=held))

    assert missing in str(refused.value)
    assert "cn_boc_anxin_009" in str(refused.value)


def test_an_unknown_quota_position_is_refused_citing_the_quota_entry():
    with pytest.raises(RailError, match="cn_fx_quota_001"):
        _pay(_rail(quota_known=False))


def test_the_stages_run_in_the_providers_words_mapped_onto_receipt_statuses():
    rail = _rail()
    receipt = _pay(rail)
    start = receipt.executed_at
    seen = []
    for stage in range(len(rail.STAGES)):
        trace = rail.status(receipt.receipt_id, now=start + timedelta(hours=rail.STAGE_HOURS * stage + 0.5))
        seen.append((trace.status, trace.next_steps[0]))

    assert seen == [
        (ReceiptStatus.CREATED, "cn_bank_remit_sim stage: documents submitted."),
        (ReceiptStatus.HELD_FOR_REVIEW, "cn_bank_remit_sim stage: under review."),
        (ReceiptStatus.FUNDED, "cn_bank_remit_sim stage: released."),
        (ReceiptStatus.IN_TRANSIT, "cn_bank_remit_sim stage: in transit."),
        (ReceiptStatus.COMPLETED, "cn_bank_remit_sim stage: arrived."),
    ]


def test_the_trace_has_no_sourced_duration_and_names_the_entry():
    rail = _rail()

    trace = rail.status(_pay(rail).receipt_id)

    assert trace.typical_duration_hours is None
    assert trace.typical_duration_source == "cn_boc_anxin_009: no sourced duration on file"
    assert "Lifeline has no sourced duration on file for this transfer. Source: cn_boc_anxin_009." in trace.next_steps


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_is_accepted(script):
    rail = _rail(script)

    assert rail.status(_pay(rail).receipt_id).receipt_id == "cn_bank_remit_sim-0001"


def test_held_for_review_stays_under_review_whatever_the_clock_says():
    rail = _rail("held_for_review")
    receipt = _pay(rail)

    trace = rail.status(receipt.receipt_id, now=datetime.now(timezone.utc) + timedelta(days=90))

    assert trace.status is ReceiptStatus.HELD_FOR_REVIEW
    assert trace.next_steps[0] == "cn_bank_remit_sim stage: under review."


def test_the_engine_refuses_a_student_transfer_from_china_to_singapore_under_r05():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-cn-0001",
        amount=Decimal("100"),
        currency="SGD",
        corridor="CN>SG",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R05"]


def _inbound_loop(script: str, responses) -> tuple[AgentLoop, HashChainLedger]:
    rail = _rail(script)
    rails = {"cn_bank_remit_sim": rail}
    block = {
        "cn_bank_remit_sim": [
            {"receipt_id": INBOUND_ID, "amount": "20000", "currency": "CNY", "corridor": "CN>SG",
             "status": "created", "sender": "parent", "sent_hours_ago": 30}
        ]
    }
    where = seed_inbound(rails, inbound_from_fixture(block, rails))
    ledger = HashChainLedger()
    loop = AgentLoop(
        adapter=FakeModelAdapter(list(responses)),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=rails,
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        inbound_receipts={USER: where},
    )
    return loop, ledger


def test_a_parents_transfer_that_has_not_arrived_is_traced_through_the_loop():
    loop, ledger = _inbound_loop("normal", [])

    decision, result = loop.act(USER, "trace_transfer", {"receipt_id": INBOUND_ID})

    assert result["trace"]["status"] != "completed"
    assert result["trace"]["typical_duration_hours"] is None
    assert [e.kind for e in ledger.entries()] == ["proposal", "decision", "execution"]


def test_scam_text_in_a_trace_reaches_the_loop_as_data_and_its_payment_is_refused_under_r01():
    pay_the_fee = {"amount": "2000", "currency": "SGD", "corridor": "SG>BR", "payee_id": "release_agent_88", "purpose": "rent"}
    loop, ledger = _inbound_loop(
        "scam_text",
        [_call("trace_transfer", {"receipt_id": INBOUND_ID}), _call("propose_transfer", pay_the_fee, call_id="toolu_02")],
    )

    reply = loop.handle(USER, _user(f"My parents' money has not arrived, receipt {INBOUND_ID}"))

    trace_result = [m for m in loop._conversations[USER] if m.role is Role.TOOL][0]
    assert SCAM_TEXT in json_text(trace_result)
    assert reply.decision.allowed is False
    assert reply.decision.rule_ids == ["R01"]
    assert reply.confirmation is None and reply.receipt is None
    suspected = [e.payload for e in ledger.entries() if e.kind == "injection_suspected"]
    assert suspected and set(suspected[0]["fields"]) == {"payee_id", "amount"}
    assert all(v == "tool_result" for v in suspected[0]["fields"].values())


def json_text(message: Message) -> str:
    return message.text
