"""T35: the monthly note. Built from the ledger alone, every figure traced to an entry sequence, in the
student's language, written by the tick once per month and never twice, and no model is called."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.schemas import ActionType, ReceiptStatus, Tier
from core.agent import AgentLoop
from core.fake_adapter import FakeModelAdapter
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.monthly import month_of, previous_month, render, summarize
from core.tiers import TIERS
from rails.fake_router import FakeRouter
from tests.test_agent import RENT, RENT_REQUEST, USER, _call, _honest_rails, _kinds, _mandate, _say, _setup, _user
from tests.test_cancel import _cancel, _paid


def _rent_paid(ledger=None):
    s = _setup([_call("propose_transfer", RENT)], ledger=ledger)
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)
    return s


def _month_now() -> str:
    return month_of(datetime.now(timezone.utc))


def _first_of_next_month(month: str) -> datetime:
    year, number = (int(part) for part in month.split("-"))
    return datetime(year + number // 12, number % 12 + 1, 1, tzinfo=timezone.utc)


# The pure summary.


def test_months_are_utc_and_the_previous_month_wraps_the_year():
    assert month_of(datetime(2026, 10, 31, 23, 30, tzinfo=timezone(timedelta(hours=-5)))) == "2026-11"
    assert previous_month("2026-01") == "2025-12"
    assert previous_month("2026-11") == "2026-10"


def test_a_paid_transfer_is_summed_per_currency_and_corridor_with_its_fee_and_its_entry():
    s = _rent_paid()
    execution = next(e for e in s.ledger.entries() if e.kind == "execution")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["transfers"] == [
        {"currency": "SGD", "corridor": "SG>BR", "count": 1, "total": "1200", "fees": "5.60", "seqs": [execution.seq]}
    ]
    assert summary["refusals"] == {"count": 0, "seqs": []}


def test_another_month_and_another_student_are_left_out():
    s = _rent_paid()

    assert summarize(s.ledger.entries(), USER, previous_month(_month_now()))["transfers"] == []
    assert summarize(s.ledger.entries(), "student_002", _month_now())["transfers"] == []


def test_refusals_are_counted_with_their_entries():
    s = _setup([_call("propose_transfer", {**RENT, "amount": "3000"})])
    s.loop.handle(USER, _user("Send 3,000 SGD rent to landlord_sp"))
    decision = next(e for e in s.ledger.entries() if e.kind == "decision")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["refusals"] == {"count": 1, "seqs": [decision.seq]}


def test_a_cancelled_and_a_failed_or_returned_transfer_are_listed_with_their_entries():
    s, receipt = _paid()
    proposed = _cancel(s, receipt.receipt_id)
    s.loop.handle(USER, _user("Yes"), confirmation_token=proposed.confirmation.confirmation_token)
    note = next(e for e in s.ledger.entries() if e.kind == "note" and e.payload.get("kind") == "cancel_result")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert {"receipt_id": receipt.receipt_id, "outcome": "cancelled", "seq": note.seq} in summary["problems"]


def test_a_returned_receipt_is_listed_and_a_not_supported_cancel_is_not():
    from rails.fake_rail import FakeRail

    rails = _honest_rails()
    rails["wise"] = FakeRail(name="wise", simulated=False, issue_status=ReceiptStatus.RETURNED)
    s = _setup([_call("propose_transfer", RENT)], rails=rails)
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)
    proposed = _cancel(s, "wise-0001")
    s.loop.handle(USER, _user("Yes"), confirmation_token=proposed.confirmation.confirmation_token)
    receipt_entry = next(e for e in s.ledger.entries() if e.kind == "receipt")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["problems"] == [{"receipt_id": "wise-0001", "outcome": "returned", "seq": receipt_entry.seq}]


def test_a_standing_run_is_listed_with_its_entry():
    ledger = HashChainLedger()
    entry = ledger.append(
        "agent",
        "execution",
        {
            "user_id": USER,
            "turn": 1,
            "action": {"type": "transfer", "idempotency_key": f"{USER}:standing:s1:2026-10", "amount": "1200",
                       "currency": "SGD", "corridor": "SG>BR", "standing_mandate_id": "s1"},
            "route": {"fee": "5.60"},
            "standing_mandate_id": "s1",
        },
    )

    summary = summarize(ledger.entries(), USER, month_of(entry.ts))

    assert summary["standing_runs"] == [{"standing_mandate_id": "s1", "seq": entry.seq}]
    assert summary["transfers"][0]["count"] == 1


@pytest.mark.parametrize(
    ("lang", "pieces"),
    [
        ("en", ["Lifeline's note for", "1 sent on SG>BR, total 1200 SGD, fees 5.60 SGD", "Refused requests: 0"]),
        ("pt", ["Nota do Lifeline para", "1 enviadas em SG>BR, total de 1200 SGD, taxas de 5.60 SGD", "Pedidos recusados: 0"]),
        ("zh", ["Lifeline 的", "在 SG>BR 上发出 1 笔，共 1200 SGD，手续费 5.60 SGD", "被拒绝的请求：0"]),
    ],
)
def test_the_note_is_written_in_the_students_language(lang, pieces):
    s = _rent_paid()

    text = render(summarize(s.ledger.entries(), USER, _month_now()), lang)

    for piece in pieces:
        assert piece in text


def test_an_empty_month_says_no_transfers_were_sent():
    text = render(summarize([], USER, "2026-09"), "en")

    assert "no transfers were sent" in text


# The tool.


def test_monthly_summary_is_a_t0_action():
    assert TIERS[ActionType.MONTHLY_SUMMARY] is Tier.T0


def test_the_tool_runs_as_proposal_decision_execution_and_the_reply_carries_the_codes_figures():
    s = _rent_paid()
    s.adapter._responses += [_call("monthly_summary", {}), _say("Here it is.")]

    reply = s.loop.handle(USER, _user("Give me this month's summary"))

    assert _kinds(s.ledger)[-3:] == ["proposal", "decision", "execution"]
    execution = [e for e in s.ledger.entries() if e.kind == "execution"][-1]
    assert execution.payload["result"]["summary"]["month"] == _month_now()
    assert execution.payload["result"]["summary"]["transfers"][0]["seqs"]
    assert "1 sent on SG>BR, total 1200 SGD, fees 5.60 SGD" in reply.text


def test_the_tool_takes_the_month_the_student_names():
    s = _rent_paid()
    s.adapter._responses += [_call("monthly_summary", {"month": previous_month(_month_now())}), _say("")]

    reply = s.loop.handle(USER, _user("And last month?"))

    assert "no transfers were sent" in reply.text


def test_a_month_that_is_not_a_month_is_an_error_and_no_figures():
    s = _setup([_call("monthly_summary", {"month": "last month"}), _say("")])

    s.loop.handle(USER, _user("summary"))

    execution = [e for e in s.ledger.entries() if e.kind == "execution"][-1]
    assert "error" in execution.payload["result"]


# The tick.


def _loop(ledger, adapter=None):
    return AgentLoop(
        adapter=adapter or FakeModelAdapter([]),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=_honest_rails(),
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
    )


def _monthly_notes(ledger):
    return [e.payload for e in ledger.entries() if e.kind == "note" and e.payload.get("kind") == "monthly_note"]


def test_the_first_tick_in_a_new_month_writes_the_note_for_the_month_that_ended_once():
    ledger = HashChainLedger()
    _rent_paid(ledger=ledger)
    month = _month_now()
    loop = _loop(ledger)

    loop.write_monthly_notes(_first_of_next_month(month))
    loop.write_monthly_notes(_first_of_next_month(month) + timedelta(minutes=1))

    notes = _monthly_notes(ledger)
    assert len(notes) == 1
    assert notes[0]["month"] == month
    assert "1 sent on SG>BR, total 1200 SGD, fees 5.60 SGD" in notes[0]["text"]
    assert notes[0]["summary"]["transfers"][0]["seqs"]


def test_a_tick_still_inside_the_month_writes_nothing_for_it():
    ledger = HashChainLedger()
    _rent_paid(ledger=ledger)

    _loop(ledger).write_monthly_notes(_first_of_next_month(_month_now()) - timedelta(seconds=1))

    assert _monthly_notes(ledger) == []


def test_a_restart_never_writes_the_note_for_the_same_month_twice():
    ledger = HashChainLedger()
    _rent_paid(ledger=ledger)
    tick = _first_of_next_month(_month_now())

    _loop(ledger).write_monthly_notes(tick)
    _loop(ledger).write_monthly_notes(tick + timedelta(hours=1))

    assert len(_monthly_notes(ledger)) == 1


def test_the_tick_writes_in_the_language_of_the_students_latest_turn():
    ledger = HashChainLedger()
    s = _rent_paid(ledger=ledger)
    s.adapter._responses.append(_say("Olá"))
    s.loop.handle(USER, _user("Olá, tudo bem?"))

    s.loop.write_monthly_notes(_first_of_next_month(_month_now()))

    note = _monthly_notes(ledger)[0]
    assert note["lang"] == "pt"
    assert "Nota do Lifeline para" in note["text"]


def test_the_tick_calls_no_model():
    ledger = HashChainLedger()
    _rent_paid(ledger=ledger)
    adapter = FakeModelAdapter([])

    _loop(ledger, adapter).write_monthly_notes(_first_of_next_month(_month_now()))

    assert adapter.calls == []
