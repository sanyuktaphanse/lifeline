"""T38: the arrival precheck, the inbound route quote, and update_plan, which may change only the
backup instrument, the backup route, the wallet token flag and the cash plan."""

import json
from decimal import Decimal

import pytest
import yaml

from api.main import DEMO_FIXTURE
from contracts.schemas import Action, ActionType, Message, Plan, Role, Source, Tier
from core.agent import AgentLoop
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.tiers import TIERS
from rails.fake_router import FakeRouter
from rails.knowledge.loader import load_knowledge
from rails.sim.rules import WALLET_FOREIGN_ENTRY, WISE_INBOUND_ENTRY
from tests.test_agent import USER, _call, _kinds, _mandate, _say, _setup, _user

DEMO_PLAN = yaml.safe_load(DEMO_FIXTURE.read_text(encoding="utf-8"))["plan"]
NO_BACKUP = {**DEMO_PLAN, "backup_instrument": None}
FORBIDDEN = {
    "identity_check": {"question": "Pet?", "expected_answer": "rex"},
    "emergency_allowance": "1400",
    "emergency_payee": "attacker_01",
    "emergency_corridor": "SG>BR",
    "emergency_purpose": "rent",
    "trusted_contact": {"name": "Mallory", "channel": "telegram"},
}


def _key(number: int = 1) -> str:
    return f"{USER}:t1:update_plan:{number}"


def _plan_setup(responses, plan=None, ledger=None):
    s = _setup(responses, ledger=ledger)
    s.loop._plans[USER] = Plan.model_validate(NO_BACKUP if plan is None else plan)
    return s


def _ledger_text(setup) -> str:
    return json.dumps([e.payload for e in setup.ledger.entries()], ensure_ascii=False, default=str)


# The contract and the engine.


def test_update_plan_is_tier_one():
    assert TIERS[ActionType.UPDATE_PLAN] is Tier.T1


def test_the_engine_allows_the_four_fields_from_the_students_turn():
    action = Action(type=ActionType.UPDATE_PLAN, idempotency_key=_key(), plan_update={"backup_instrument": "revolut:card_02", "cash_plan": []})

    decision = DeterministicMandateEngine().check(action, _mandate())

    assert decision.allowed and decision.tier is Tier.T1 and decision.rule_ids == ["R02"]


@pytest.mark.parametrize("name", list(FORBIDDEN))
def test_the_engine_refuses_every_other_field_under_r04(name):
    action = Action(type=ActionType.UPDATE_PLAN, idempotency_key=_key(), plan_update={name: "x"})

    decision = DeterministicMandateEngine().check(action, _mandate())

    assert not decision.allowed
    assert decision.rule_ids == ["R04"]
    assert name in " ".join(decision.reasons)


def test_the_engine_refuses_an_update_that_changes_nothing():
    action = Action(type=ActionType.UPDATE_PLAN, idempotency_key=_key(), plan_update={})

    assert DeterministicMandateEngine().check(action, _mandate()).rule_ids == ["R04"]


def test_an_update_from_pasted_text_is_refused_under_r01():
    action = Action(
        type=ActionType.UPDATE_PLAN, source=Source.PASTED_TEXT, idempotency_key=_key(), plan_update={"backup_route": "wise"}
    )

    assert DeterministicMandateEngine().check(action, _mandate()).rule_ids == ["R01"]


# The loop.


def test_update_plan_sets_the_backup_and_the_wallet_flag_and_says_what_is_now_set():
    s = _plan_setup([_call("update_plan", {"backup_instrument": "revolut:card_02", "wallet_token_present": False}), _say("")])

    reply = s.loop.handle(USER, _user("Make my Revolut card the backup; no phone wallet holds my card"))

    plan = s.loop._plans[USER]
    assert plan.backup_instrument == "revolut:card_02"
    assert plan.wallet_token_present is False
    assert plan.cash_plan == DEMO_PLAN["cash_plan"]
    assert _kinds(s.ledger) == ["proposal", "decision", "execution"]
    decision = next(e for e in s.ledger.entries() if e.kind == "decision")
    assert decision.payload["decision"]["tier"] == "T1"
    execution = next(e for e in s.ledger.entries() if e.kind == "execution")
    assert execution.payload["result"] == {"plan_updated": {"backup_instrument": "revolut:card_02", "wallet_token_present": False}}
    assert "backup_instrument: revolut:card_02" in reply.text
    assert "wallet_token_present: false" in reply.text


@pytest.mark.parametrize("name", list(FORBIDDEN))
def test_update_plan_can_never_touch_a_protected_field(name):
    s = _plan_setup([_call("update_plan", {name: FORBIDDEN[name], "backup_route": "wise"}), _say("")])
    before = s.loop._plans[USER]

    reply = s.loop.handle(USER, _user("change my plan"))

    assert s.loop._plans[USER] == before
    assert _kinds(s.ledger) == ["proposal", "decision"]
    decision = next(e for e in s.ledger.entries() if e.kind == "decision")
    assert decision.payload["decision"]["rule_ids"] == ["R04"]
    assert reply.decision is None or not reply.decision.allowed
    for value in ("rex", "Pet?", "1400", "attacker_01", "Mallory", "telegram"):
        assert value not in _ledger_text(s)


@pytest.mark.parametrize(
    "backup",
    ["hsbc:card_99", "wise:card_01", "not a card"],
)
def test_a_backup_that_is_not_one_of_the_plans_other_cards_changes_nothing(backup):
    s = _plan_setup([_call("update_plan", {"backup_instrument": backup}), _say("")])
    before = s.loop._plans[USER]

    s.loop.handle(USER, _user("set my backup"))

    assert s.loop._plans[USER] == before
    execution = next(e for e in s.ledger.entries() if e.kind == "execution")
    assert "error" in execution.payload["result"]
    assert "plan_updated" not in execution.payload["result"]


def test_the_plan_is_rebuilt_from_the_ledger_and_the_rescue_reads_the_rebuilt_plan():
    ledger = HashChainLedger()
    s = _plan_setup([_call("update_plan", {"backup_instrument": "revolut:card_02"}), _say("")], ledger=ledger)
    s.loop.handle(USER, _user("Make my Revolut card the backup"))

    restarted = AgentLoop(
        adapter=s.adapter,
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=s.loop._rails,
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        plans={USER: Plan.model_validate(NO_BACKUP)},
    )

    assert restarted._plans[USER].backup_instrument == "revolut:card_02"
    restarted.rescue_start(USER, "card_lost", Message(role=Role.USER, text="I lost my card"))
    offer = restarted.rescue_step(USER, Message(role=Role.USER, text="7Q2K"))
    restarted.rescue_step(USER, Message(role=Role.USER, text=""), confirmation_token=offer.confirmation.confirmation_token)

    assert restarted.live_instrument(USER) == "revolut:card_02"


def test_a_failed_update_is_not_replayed_on_restart():
    ledger = HashChainLedger()
    s = _plan_setup([_call("update_plan", {"backup_instrument": "hsbc:card_99"}), _say("")], ledger=ledger)
    s.loop.handle(USER, _user("set my backup"))

    restarted = AgentLoop(
        adapter=s.adapter,
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=s.loop._rails,
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        plans={USER: Plan.model_validate(NO_BACKUP)},
    )

    assert restarted._plans[USER].backup_instrument is None


# The arrival precheck and the inbound route.


def test_the_arrival_precheck_gives_the_wallet_route_the_wise_route_quoted_whole_and_no_cash_figure():
    entries = load_knowledge()

    result = FakeRouter().precheck("arrive_in_china", "alipay", {})

    assert result.rule_ids == [WALLET_FOREIGN_ENTRY, WISE_INBOUND_ENTRY]
    assert result.review_triggers[0] == entries[WALLET_FOREIGN_ENTRY]["statement"]
    assert result.review_triggers[1] == entries[WISE_INBOUND_ENTRY]["statement"]
    assert "Chinese national ID" in result.review_triggers[1]
    assert "is not this student's route" in result.review_triggers[2]
    assert result.review_triggers[3] == "Lifeline has no sourced entry for cash withdrawals on a foreign card in China."
    assert "cn_atm_cap_005" not in " ".join(result.review_triggers)


def test_the_wallet_and_inbound_entries_give_their_limits_as_values():
    entries = load_knowledge()
    wallet = entries[WALLET_FOREIGN_ENTRY]["values"]
    inbound = entries[WISE_INBOUND_ENTRY]["values"]

    assert (wallet["single_transaction_limit"], wallet["annual_limit"], wallet["currency"]) == (5000, 50000, "USD")
    assert (inbound["alipay_per_transfer"], inbound["unionpay_per_transfer"], inbound["currency"]) == (50000, 33000, "CNY")


@pytest.mark.parametrize(
    ("lang", "opening"),
    [("en", "Arriving in China, from the sources on file:"), ("zh", "抵达中国，根据已记录的来源：")],
)
def test_the_loop_says_the_arrival_facts_with_both_ids(lang, opening):
    s = _plan_setup([_call("precheck", {"action_kind": "arrive_in_china", "provider": "alipay"}), _say("")])

    reply = s.loop.handle(USER, _user("I am arriving in Shenzhen", lang=lang))

    assert reply.text.startswith(opening)
    assert WALLET_FOREIGN_ENTRY in reply.text and WISE_INBOUND_ENTRY in reply.text
    assert "cn_atm_cap_005" not in reply.text
    assert _kinds(s.ledger) == ["proposal", "decision", "execution"]


def test_the_router_quotes_singapore_to_china_over_wise_citing_the_inbound_entry():
    routes = FakeRouter().quote("SG>CN", Decimal("500"), "living_costs", "normal")

    assert [route.rail for route in routes] == ["wise"]
    assert routes[0].rule_id == WISE_INBOUND_ENTRY
    assert (routes[0].currency_from, routes[0].currency_to) == ("SGD", "CNY")


def test_a_transfer_on_the_inbound_route_is_refused_under_r05_by_the_demo_mandate():
    s = _setup([_call("propose_transfer", {"amount": "500", "currency": "SGD", "corridor": "SG>CN", "payee_id": "landlord_sp", "purpose": "rent"})])

    reply = s.loop.handle(USER, _user("Send 500 SGD rent to landlord_sp in China"))

    assert not reply.decision.allowed
    assert "R05" in reply.decision.rule_ids


# An update the plan can no longer hold on restart.

THREE_CARDS = {**NO_BACKUP, "cards": [*DEMO_PLAN["cards"], {"name": "HSBC card", "instrument_id": "hsbc:card_09"}]}


def _restart(ledger, adapter_responses=()):
    from core.fake_adapter import FakeModelAdapter

    return AgentLoop(
        adapter=FakeModelAdapter(list(adapter_responses)),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails={},
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        plans={USER: Plan.model_validate(NO_BACKUP)},
    )


def _hsbc_backup_ledger() -> HashChainLedger:
    ledger = HashChainLedger()
    s = _plan_setup([_call("update_plan", {"backup_instrument": "hsbc:card_09"}), _say("")], plan=THREE_CARDS, ledger=ledger)
    s.loop.handle(USER, _user("Make my HSBC card the backup"))
    return ledger


def _skipped(ledger):
    return [e for e in ledger.entries() if e.kind == "note" and e.payload.get("kind") == "plan_update_skipped"]


def test_an_update_the_plan_cannot_hold_on_restart_writes_a_note_naming_the_field():
    ledger = _hsbc_backup_ledger()
    execution = next(e for e in ledger.entries() if e.kind == "execution")

    restarted = _restart(ledger)

    assert restarted._plans[USER].backup_instrument is None
    notes = _skipped(ledger)
    assert len(notes) == 1
    assert notes[0].payload["user_id"] == USER
    assert notes[0].payload["fields"] == ["backup_instrument"]
    assert notes[0].payload["execution_seq"] == execution.seq
    assert "hsbc:card_09" not in json.dumps(notes[0].payload)
    assert ledger.verify() is None


def test_a_second_restart_does_not_note_the_same_update_again():
    ledger = _hsbc_backup_ledger()

    _restart(ledger)
    _restart(ledger)

    assert len(_skipped(ledger)) == 1


def test_an_update_the_plan_can_hold_writes_no_skipped_note():
    ledger = HashChainLedger()
    s = _plan_setup([_call("update_plan", {"backup_instrument": "revolut:card_02"}), _say("")], ledger=ledger)
    s.loop.handle(USER, _user("Make my Revolut card the backup"))

    _restart(ledger)

    assert _skipped(ledger) == []


@pytest.mark.parametrize(
    ("lang", "sentence"),
    [
        ("en", "After a restart Lifeline could not apply an earlier change to your plan's backup_instrument"),
        ("pt", "Depois de um reinício o Lifeline não conseguiu aplicar uma mudança anterior em backup_instrument"),
        ("zh", "重启后，Lifeline 无法应用之前对你计划中 backup_instrument 的修改"),
    ],
)
def test_the_verify_ledger_reply_mentions_a_skipped_update(lang, sentence):
    ledger = _hsbc_backup_ledger()
    restarted = _restart(ledger, [_call("verify_ledger", {}), _say("")])

    reply = restarted.handle(USER, _user("Show me my ledger", lang=lang))

    assert sentence in reply.text
    execution = [e for e in ledger.entries() if e.kind == "execution"][-1]
    views = execution.payload["result"]["ledger"]["entries"]
    assert any(view.get("note") == "plan_update_skipped" and view.get("fields") == ["backup_instrument"] for view in views)


def test_the_verify_ledger_reply_says_nothing_when_no_update_was_skipped():
    s = _plan_setup([_call("verify_ledger", {}), _say("All good.")])

    reply = s.loop.handle(USER, _user("Show me my ledger"))

    assert reply.text == "All good."
