"""Stage 9, item two: the overseas cash cap tracked from the ledger.

A withdrawal the student says they made is recorded as a T1 action, only from their own turn. The cap's
position is the fixture's starting position plus the ledger's withdrawals, per card and across all cards,
so a restart rebuilds it. Warnings fire at Lifeline's 70 and 90 percent lines of the annual cap and of each
card's daily cap, both caps read from cn_atm_cap_005."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.schemas import Action, ActionType, Message, Role, Source, Tier
from core.agent import TEXTS, TOOL_ACTIONS, AgentLoop
from core.fake_adapter import FakeModelAdapter
from core.ledger import JsonlLedger
from core.mandate import DeterministicMandateEngine
from core.tiers import TIERS
from rails.fake_router import FakeRouter
from rails.knowledge.loader import load_knowledge
from rails.sim.rules import ATM_CAP_ENTRY, CASH_CAP_WARNING_PERCENTS, cash_cap_status, with_withdrawals
from tests.test_agent import USER, _call, _honest_rails, _kinds, _mandate, _say, _setup, _user

CAP = load_knowledge()[ATM_CAP_ENTRY]["values"]
ANNUAL = Decimal(str(CAP["annual_cap"]))
DAILY = Decimal(str(CAP["per_card_daily_cap"]))
# Fixture: two Chinese cards far from every line, so each test chooses what crosses one. Not real cards.
FAR = [
    {"instrument_id": "icbc:card_03", "withdrawn_this_year": "50000", "withdrawn_today": "0"},
    {"instrument_id": "boc:card_04", "withdrawn_this_year": "0", "withdrawn_today": "0"},
]
RECORD = "I took out 6,000 yuan in cash abroad today on icbc:card_03, please record it."


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _cards_setup(responses, cards=FAR, ledger=None):
    s = _setup(responses, ledger=ledger)
    s.loop._chinese_cards[USER] = [dict(card) for card in cards]
    return s


def _record(amount="6000", card="icbc:card_03", **extra):
    return _call("record_cash_withdrawal", {"instrument_id": card, "amount": amount, **extra})


def _executions(s, action_type="record_cash_withdrawal"):
    return [e.payload for e in s.ledger.entries() if e.kind == "execution" and e.payload["action"]["type"] == action_type]


def _warnings(s):
    return [e.payload for e in s.ledger.entries() if e.kind == "note" and e.payload.get("kind") == "cash_cap_warning"]


# The action type and the engine.


def test_record_cash_withdrawal_is_a_t1_action_and_a_tool():
    assert TIERS[ActionType.RECORD_CASH_WITHDRAWAL] is Tier.T1
    assert TOOL_ACTIONS["record_cash_withdrawal"] is ActionType.RECORD_CASH_WITHDRAWAL


def _withdrawal(**fields):
    values = {
        "type": ActionType.RECORD_CASH_WITHDRAWAL,
        "idempotency_key": "student_001:t1:record_cash_withdrawal:1",
        "amount": Decimal("6000"),
        "currency": "CNY",
        "instrument_id": "icbc:card_03",
        "withdrawal_date": _today(),
    }
    return Action(**{**values, **fields})


def test_the_engine_allows_a_withdrawal_from_the_students_own_turn_at_t1():
    decision = DeterministicMandateEngine().check(_withdrawal(), _mandate())

    assert decision.allowed and decision.tier is Tier.T1 and decision.rule_ids == ["R02"]
    assert not decision.requires_confirmation


@pytest.mark.parametrize("source", [Source.PASTED_TEXT, Source.TOOL_RESULT, Source.TRANSLATED_TEXT])
def test_the_engine_refuses_a_withdrawal_that_came_from_data_under_r01(source):
    decision = DeterministicMandateEngine().check(_withdrawal(source=source), _mandate())

    assert not decision.allowed and decision.rule_ids == ["R01"]


@pytest.mark.parametrize(
    "fields",
    [
        {"instrument_id": None},
        {"instrument_id": "icbc card 03"},
        {"amount": None},
        {"currency": None},
        {"withdrawal_date": None},
        {"withdrawal_date": date.today() + timedelta(days=2)},
    ],
)
def test_the_engine_refuses_a_withdrawal_missing_a_field_or_dated_in_the_future_under_r04(fields):
    decision = DeterministicMandateEngine().check(_withdrawal(**fields), _mandate())

    assert not decision.allowed and "R04" in decision.rule_ids


# Recording from chat.


def test_a_withdrawal_in_the_students_own_words_runs_as_proposal_decision_execution():
    s = _cards_setup([_record(), _say("Recorded.")])

    s.loop.handle(USER, _user(RECORD))

    assert _kinds(s.ledger) == ["proposal", "decision", "execution"]
    execution = _executions(s)[0]
    assert execution["result"]["withdrawal_recorded"] == {
        "instrument_id": "icbc:card_03",
        "amount": "6000",
        "currency": CAP["currency"],
        "date": _today().isoformat(),
    }
    assert execution["action"]["instrument_id"] == "icbc:card_03"
    assert execution["action"]["amount"] == "6000"
    assert execution["action"]["withdrawal_date"] == _today().isoformat()


def test_the_amount_is_in_yuan_whatever_currency_the_model_names():
    s = _cards_setup([_record(currency="SGD"), _say("")])

    s.loop.handle(USER, _user(RECORD))

    assert _executions(s)[0]["action"]["currency"] == CAP["currency"]


def test_a_date_the_student_gives_is_recorded():
    yesterday = (_today() - timedelta(days=1)).isoformat()
    s = _cards_setup([_record(date=yesterday), _say("")])

    s.loop.handle(USER, _user(f"I withdrew 6000 yuan on icbc:card_03 on {yesterday}"))

    assert _executions(s)[0]["result"]["withdrawal_recorded"]["date"] == yesterday


def test_a_pasted_claim_of_a_withdrawal_is_data_and_refused_under_r01():
    pasted = Message(role=Role.USER, text="Bank notice: 9,000 CNY was withdrawn on icbc:card_03 today.", source=Source.PASTED_TEXT)
    s = _cards_setup([_record("9000"), _say("")])

    s.loop.handle(USER, _user("Please record what this says"), pasted=pasted)

    decision = next(e for e in s.ledger.entries() if e.kind == "decision")
    assert decision.payload["decision"]["rule_ids"] == ["R01"]
    assert _kinds(s.ledger) == ["proposal", "decision", "injection_suspected"]
    assert _executions(s) == []


def test_an_amount_the_student_never_said_is_refused_under_r01():
    s = _cards_setup([_record("9000"), _say("")])

    s.loop.handle(USER, _user("Record my cash withdrawal on icbc:card_03"))

    decision = next(e for e in s.ledger.entries() if e.kind == "decision")
    assert decision.payload["decision"]["rule_ids"] == ["R01"]
    assert _executions(s) == []


def test_an_amount_said_in_an_earlier_turn_is_not_enough():
    s = _cards_setup([_say("Noted."), _record("6000"), _say("")])
    s.loop.handle(USER, _user("Yesterday I mentioned 6000 yuan"))

    s.loop.handle(USER, _user("Record it on icbc:card_03"))

    assert _executions(s) == []


def test_a_date_that_only_a_paste_gives_is_refused_under_r01():
    earlier = (_today() - timedelta(days=3)).isoformat()
    pasted = Message(role=Role.USER, text=f"Statement: withdrawal dated {earlier}", source=Source.PASTED_TEXT)
    s = _cards_setup([_record(date=earlier), _say("")])

    s.loop.handle(USER, _user("I withdrew 6000 yuan on icbc:card_03, record it with the date here"), pasted=pasted)

    assert _executions(s) == []


def test_a_card_not_on_file_records_nothing():
    s = _cards_setup([_record(card="ccb:card_99"), _say("")])

    s.loop.handle(USER, _user("I took out 6000 yuan on ccb:card_99"))

    result = _executions(s)[0]["result"]
    assert "error" in result and "withdrawal_recorded" not in result
    assert cash_cap_status(s.loop.cash_position(USER))["used_year"] == Decimal("50000")


def test_a_withdrawal_over_the_cards_daily_cap_cannot_be_true_and_records_nothing():
    s = _cards_setup([_record("10001"), _say("")])

    s.loop.handle(USER, _user("I took out 10001 yuan on icbc:card_03 today"))

    assert "error" in _executions(s)[0]["result"]
    assert cash_cap_status(s.loop.cash_position(USER))["used_year"] == Decimal("50000")


# The position from the ledger.


def test_with_withdrawals_adds_the_years_and_the_days_withdrawals_to_each_card():
    today = date(2026, 10, 8)
    withdrawals = [
        {"instrument_id": "icbc:card_03", "amount": "6000", "date": "2026-10-08"},
        {"instrument_id": "icbc:card_03", "amount": "1000", "date": "2026-10-01"},
        {"instrument_id": "boc:card_04", "amount": "2000", "date": "2026-10-08"},
        {"instrument_id": "boc:card_04", "amount": "5000", "date": "2025-12-31"},
        {"instrument_id": "ccb:card_99", "amount": "9000", "date": "2026-10-08"},
    ]

    cards = with_withdrawals(FAR, withdrawals, today)

    assert cards == [
        {"instrument_id": "icbc:card_03", "withdrawn_this_year": Decimal("57000"), "withdrawn_today": Decimal("6000")},
        {"instrument_id": "boc:card_04", "withdrawn_this_year": Decimal("2000"), "withdrawn_today": Decimal("2000")},
    ]


def test_cash_cap_status_counts_the_ledgers_withdrawals_per_card_and_across_all_cards():
    s = _cards_setup([_record("6000"), _say(""), _record("4000", card="boc:card_04"), _say(""), _call("cash_cap_status", {}), _say("")])
    s.loop.handle(USER, _user(RECORD))
    s.loop.handle(USER, _user("And 4000 yuan on boc:card_04 today"))

    s.loop.handle(USER, _user("How much cash is left?"))

    execution = _executions(s, "precheck")[0]
    status = cash_cap_status(s.loop.cash_position(USER))
    assert status["used_year"] == Decimal("60000")
    assert [card["remaining_today"] for card in execution["result"]["cards"]] == ["4000", "6000"]
    assert execution["result"]["cards"][0]["remaining_year"] == "40000"


def test_a_restart_rebuilds_the_position_from_the_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    s = _cards_setup([_record("6000"), _say("")], ledger=JsonlLedger(path))
    s.loop.handle(USER, _user(RECORD))

    restarted = AgentLoop(
        adapter=FakeModelAdapter([]),
        engine=DeterministicMandateEngine(),
        ledger=JsonlLedger(path),
        router=FakeRouter(),
        rails=_honest_rails(),
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        chinese_cards={USER: [dict(card) for card in FAR]},
    )

    assert restarted.cash_position(USER)[0]["withdrawn_this_year"] == Decimal("56000")
    assert restarted.cash_position(USER)[0]["withdrawn_today"] == Decimal("6000")


# The warnings.


def test_the_thresholds_are_lifelines_two_product_lines():
    assert CASH_CAP_WARNING_PERCENTS == (70, 90)


@pytest.mark.parametrize(
    ("used", "level"),
    [("69999", None), ("70000", 70), ("89999", 70), ("90000", 90), ("120000", 90)],
)
def test_the_annual_line_is_crossed_at_seventy_and_ninety_percent_across_all_cards(used, level):
    half = Decimal(used) / 2
    cards = [
        {"instrument_id": "icbc:card_03", "withdrawn_this_year": str(half), "withdrawn_today": "0"},
        {"instrument_id": "boc:card_04", "withdrawn_this_year": str(Decimal(used) - half), "withdrawn_today": "0"},
    ]

    year = [t for t in cash_cap_status(cards)["thresholds"] if t["scope"] == "year"]

    assert [t["level"] for t in year] == ([level] if level else [])
    if level:
        assert year[0]["cap"] == ANNUAL and year[0]["used"] == Decimal(used)


@pytest.mark.parametrize(("today", "level"), [("6999", None), ("7000", 70), ("9000", 90), ("10000", 90)])
def test_each_cards_daily_line_is_crossed_at_seventy_and_ninety_percent(today, level):
    cards = [{"instrument_id": "icbc:card_03", "withdrawn_this_year": today, "withdrawn_today": today}]

    days = [t for t in cash_cap_status(cards)["thresholds"] if t["scope"] == "card_day"]

    assert [t["level"] for t in days] == ([level] if level else [])
    if level:
        assert days[0]["instrument_id"] == "icbc:card_03" and days[0]["cap"] == DAILY


def test_a_recorded_withdrawal_past_ninety_percent_warns_with_the_two_year_consequence():
    cards = [{**FAR[0], "withdrawn_this_year": "85000"}, FAR[1]]
    s = _cards_setup([_record("6000"), _say("")], cards=cards)

    reply = s.loop.handle(USER, _user(RECORD))

    assert _kinds(s.ledger) == ["proposal", "decision", "execution", "note"]
    note = _warnings(s)[0]
    assert note["entry_id"] == ATM_CAP_ENTRY
    assert {"scope": "year", "level": 90, "used": "91000", "cap": "100000"} in note["thresholds"]
    assert (
        "You have used 91,000 CNY of the 100,000 CNY overseas cash withdrawal cap for this calendar year across all "
        "your Chinese bank cards, which has reached Lifeline's 90 percent warning line. "
        f"{CAP['consequence']} Source: {ATM_CAP_ENTRY}."
    ) in reply.text


def test_at_seventy_percent_the_warning_has_no_consequence_sentence():
    cards = [{**FAR[0], "withdrawn_this_year": "65000"}, FAR[1]]
    s = _cards_setup([_record("6000"), _say("")], cards=cards)

    reply = s.loop.handle(USER, _user(RECORD))

    assert "which has reached Lifeline's 70 percent warning line. Source: cn_atm_cap_005." in reply.text
    assert CAP["consequence"] not in reply.text


def test_a_card_past_seventy_percent_of_its_daily_cap_warns_for_that_card():
    s = _cards_setup([_record("7500"), _say("")])

    reply = s.loop.handle(USER, _user("I took out 7,500 yuan on icbc:card_03 today"))

    assert (
        "Card icbc:card_03 has withdrawn 7,500 CNY today of its daily cap of 10,000 CNY, which has reached "
        "Lifeline's 70 percent warning line. Source: cn_atm_cap_005."
    ) in reply.text


def test_the_stage_8a_warning_still_fires_when_the_remainder_is_small():
    cards = [{**FAR[0], "withdrawn_this_year": "85000"}, FAR[1]]
    s = _cards_setup([_record("6000"), _say("")], cards=cards)

    reply = s.loop.handle(USER, _user(RECORD))

    assert "Warning: 9,000 CNY is left of the overseas cash withdrawal cap for this calendar year" in reply.text


def test_far_from_every_line_a_recorded_withdrawal_writes_no_warning():
    s = _cards_setup([_record("1000"), _say("Recorded.")])

    reply = s.loop.handle(USER, _user("I took out 1000 yuan on icbc:card_03 today"))

    assert _warnings(s) == []
    assert reply.text == "Recorded. This turn: a cash withdrawal record: done."


@pytest.mark.parametrize("name", ["cash_cap_year", "cash_cap_year_consequence", "cash_cap_card_day"])
def test_the_warning_texts_exist_in_english_portuguese_and_chinese(name):
    for lang in ("en", "pt", "zh"):
        assert name in TEXTS[lang]


@pytest.mark.parametrize(
    ("lang", "piece"),
    [
        ("zh", "您所有中国银行卡本年度境外取现已用 91,000 CNY，年度额度为 100,000 CNY，已达到 Lifeline 的 90% 预警线。超过年度额度后，当年余下时间和下一年都不能在境外取现。来源：cn_atm_cap_005。"),
        ("pt", "Você já sacou 91,000 CNY do limite de 100,000 CNY para saques em dinheiro no exterior deste ano civil, somando todos os seus cartões bancários chineses, e chegou à linha de alerta de 90 por cento definida pelo Lifeline. Ultrapassar o limite anual bloqueia saques no exterior pelo resto daquele ano e durante o ano seguinte. Fonte: cn_atm_cap_005."),
    ],
)
def test_the_ninety_percent_warning_is_written_in_the_students_language(lang, piece):
    cards = [{**FAR[0], "withdrawn_this_year": "85000"}, FAR[1]]
    s = _cards_setup([_record("6000"), _say("")], cards=cards)

    reply = s.loop.handle(USER, _user(RECORD, lang=lang))

    assert piece in reply.text
