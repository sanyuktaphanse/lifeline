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
        {"currency": "SGD", "corridor": "SG>BR", "count": 1, "total": "1200", "fees": "5.60", "spread": "0",
         "seqs": [execution.seq]}
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
        ("en", ["Lifeline's note for", "1 sent on SG>BR, total 1200 SGD, fees 5.60 SGD", "refused requests 0"]),
        ("pt", ["Nota do Lifeline para", "1 enviada(s) em SG>BR, total de 1200 SGD, taxas de 5.60 SGD", "pedidos recusados 0"]),
        ("zh", ["Lifeline 的", "在 SG>BR 上发出 1 笔，共 1200 SGD，手续费 5.60 SGD", "被拒绝的请求 0 次"]),
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


# Stage 9: the spread, the taxes, the routes and the saving, the unusual, and what is coming.

from core.monthly import next_month, seqs_of  # noqa: E402

QUOTE = {"corridor": "SG>BR", "amount": "1200", "currency": "SGD", "purpose": "rent"}


def _quoted_and_paid(quote=QUOTE):
    """Rent quoted with get_quote and proposed in the same turn, then confirmed."""
    s = _setup([_call("get_quote", quote), _call("propose_transfer", RENT, call_id="toolu_02")])
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)
    return s


def _execution(ledger, *, turn=1, rail="wise", fee="5.60", spread="0", tax_lines=None, key="k:t1:propose_transfer:1"):
    return ledger.append(
        "agent",
        "execution",
        {
            "user_id": USER,
            "turn": turn,
            "action": {"type": "transfer", "idempotency_key": key, "amount": "1200", "currency": "SGD",
                       "corridor": "SG>BR"},
            "route": {"rail": rail, "fee": fee, "spread_cost": spread, "tax_lines": tax_lines or []},
            "idempotency_key": key,
        },
    )


def _note(ledger, **payload):
    return ledger.append("agent", "note", {"user_id": USER, "turn": 1, **payload})


def test_the_spread_paid_is_summed_from_the_route_each_execution_recorded():
    ledger = HashChainLedger()
    first = _execution(ledger, spread="30.00", key="k:t1:propose_transfer:1")
    second = _execution(ledger, spread="1.50", key="k:t2:propose_transfer:1", turn=2)

    summary = summarize(ledger.entries(), USER, month_of(first.ts))

    assert summary["transfers"][0]["spread"] == "31.50"
    assert summary["transfers"][0]["seqs"] == [first.seq, second.seq]
    assert "Exchange cost paid: 31.50 SGD on SG>BR." in render(summary, "en")


def test_no_tax_figure_is_on_file_when_no_route_carries_one_and_no_zero_is_invented():
    s = _rent_paid()

    summary = summarize(s.ledger.entries(), USER, _month_now())
    text = render(summary, "en")

    assert summary["taxes"] == {"on_file": False, "seqs": []}
    assert "Taxes: no tax figure is on file, because no route or entry carries one." in text
    assert "0 tax" not in text


def test_tax_lines_on_a_route_are_named_by_their_entry_and_never_totalled():
    ledger = HashChainLedger()
    entry = _execution(ledger, tax_lines=[{"name": "iof", "amount": "3.50"}])

    summary = summarize(ledger.entries(), USER, month_of(entry.ts))

    assert summary["taxes"] == {"on_file": True, "seqs": [entry.seq]}
    assert f"Taxes: tax lines are on file in entries {entry.seq}, and Lifeline does not total them." in render(summary, "en")
    assert "3.50" not in render(summary, "en")


def test_routes_used_are_counted_per_rail_with_their_entries():
    ledger = HashChainLedger()
    wise = _execution(ledger, rail="wise", key="k:t1:propose_transfer:1")
    wire = _execution(ledger, rail="bank_wire", fee="25", spread="30.00", key="k:t2:propose_transfer:1", turn=2)

    summary = summarize(ledger.entries(), USER, month_of(wise.ts))

    assert summary["routes"] == [{"rail": "wise", "count": 1, "seqs": [wise.seq]}, {"rail": "bank_wire", "count": 1, "seqs": [wire.seq]}]
    assert "Routes used: 1 over wise, 1 over bank_wire." in render(summary, "en")


def test_the_saving_against_the_bank_wire_is_computed_from_a_quote_in_the_same_turn():
    s = _quoted_and_paid()
    quote = next(e for e in s.ledger.entries() if e.kind == "execution" and e.payload["action"]["type"] == "get_quote")
    execution = next(e for e in s.ledger.entries() if e.kind == "execution" and "route" in e.payload)
    wire = next(route for route in quote.payload["result"]["routes"] if route["rail"] == "bank_wire")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    expected = Decimal(wire["fee"]) + Decimal(wire["spread_cost"]) - Decimal("5.60")
    assert summary["comparisons"] == [
        {
            "seq": execution.seq,
            "rail": "wise",
            "amount": "1200",
            "currency": "SGD",
            "compared": True,
            "quote_seq": quote.seq,
            "bank_wire_cost": format(Decimal(wire["fee"]) + Decimal(wire["spread_cost"]), "f"),
            "route_cost": "5.60",
            "saving": format(expected, "f"),
        }
    ]
    assert f"wise for 1200 SGD cost {expected} SGD less than the bank wire quoted in the same turn" in render(summary, "en")


def test_without_a_quote_in_that_turn_the_note_says_no_comparison_is_on_file():
    s = _rent_paid()
    execution = next(e for e in s.ledger.entries() if e.kind == "execution")

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["comparisons"] == [
        {"seq": execution.seq, "rail": "wise", "amount": "1200", "currency": "SGD", "compared": False}
    ]
    assert "Against the bank wire: no comparison is on file for wise for 1200 SGD." in render(summary, "en")


def test_a_quote_for_another_amount_in_the_same_turn_is_not_a_comparison():
    s = _quoted_and_paid({**QUOTE, "amount": "1000"})

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["comparisons"][0]["compared"] is False


def test_a_quote_in_an_earlier_turn_is_not_a_comparison():
    s = _setup([_call("get_quote", QUOTE), _say("Quoted."), _call("propose_transfer", RENT)])
    s.loop.handle(USER, _user("Quote 1,200 SGD rent to Brazil"))
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["comparisons"][0]["compared"] is False


def test_a_quote_without_a_bank_wire_route_is_not_a_comparison():
    ledger = HashChainLedger()
    ledger.append(
        "agent",
        "execution",
        {"user_id": USER, "turn": 1, "action": {"type": "get_quote", "idempotency_key": "k:t1:get_quote:1",
                                               "amount": "1200", "corridor": "SG>BR"},
         "result": {"routes": [{"rail": "wise", "corridor": "SG>BR", "amount": "1200", "fee": "5.60", "spread_cost": "0"}]}},
    )
    entry = _execution(ledger)

    assert summarize(ledger.entries(), USER, month_of(entry.ts))["comparisons"][0]["compared"] is False


def test_a_cancelled_or_returned_transfer_has_no_route_spread_or_saving_line():
    s, receipt = _paid()
    proposed = _cancel(s, receipt.receipt_id)
    s.loop.handle(USER, _user("Yes"), confirmation_token=proposed.confirmation.confirmation_token)

    summary = summarize(s.ledger.entries(), USER, _month_now())

    assert summary["transfers"] == []
    assert summary["routes"] == []
    assert summary["comparisons"] == []


def test_the_unusual_counts_payees_added_rescues_started_refusals_and_injections_with_their_entries():
    ledger = HashChainLedger()
    payee = _note(ledger, kind="payee_added", payee_id="new_flatmate")
    rescue = _note(ledger, kind="rescue_started", trigger="card_lost")
    refused = ledger.append("agent", "decision", {"user_id": USER, "turn": 1, "decision": {"allowed": False}})
    injection = ledger.append("agent", "injection_suspected", {"user_id": USER, "turn": 1, "fields": {"amount": "pasted_text"}})

    summary = summarize(ledger.entries(), USER, month_of(payee.ts))

    assert summary["refusals"] == {"count": 1, "seqs": [refused.seq]}
    assert summary["unusual"] == {
        "payees_added": {"count": 1, "seqs": [payee.seq]},
        "rescues_started": {"count": 1, "seqs": [rescue.seq]},
        "injection_suspected": {"count": 1, "seqs": [injection.seq]},
    }
    assert "Unusual: refused requests 1, payees added 1, rescues started 1, suspected injections 1." in render(summary, "en")


def _standing_note(ledger, standing_id="s1", schedule="monthly:5", active=True):
    return _note(
        ledger,
        kind="standing_created",
        standing_mandate={"id": standing_id, "payee_id": "landlord_sp", "amount": "1200", "schedule": schedule,
                          "corridor": "SG>BR", "purpose": "rent", "active": active},
        action={"type": "create_standing_mandate", "currency": "SGD"},
    )


def test_what_is_coming_lists_each_standing_run_due_next_month_with_its_entry():
    ledger = HashChainLedger()
    created = _standing_note(ledger)
    month = month_of(created.ts)
    following = next_month(month)

    summary = summarize(ledger.entries(), USER, month)

    assert summary["coming"]["month"] == following
    assert summary["coming"]["standing_runs"] == [
        {"standing_mandate_id": "s1", "due": f"{following}-05", "amount": "1200", "currency": "SGD",
         "payee_id": "landlord_sp", "seq": created.seq}
    ]
    assert f"Coming in {following}: a standing run of 1200 SGD to landlord_sp due {following}-05." in render(summary, "en")


def test_a_stopped_standing_mandate_or_a_cancelled_run_is_not_coming():
    ledger = HashChainLedger()
    _standing_note(ledger, "s1")
    _standing_note(ledger, "s2")
    created = _standing_note(ledger, "s3")
    month = month_of(created.ts)
    ledger.append("agent", "execution", {"user_id": USER, "turn": 2, "action": {"type": "deactivate_standing_mandate"},
                                         "result": {"deactivated": {"standing_mandate_id": "s1", "new_mandate_id": "m-v2"}}})
    ledger.append("agent", "execution", {"user_id": USER, "turn": 3, "action": {"type": "cancel_standing_run"},
                                         "result": {"cancelled": {"standing_mandate_id": "s2", "period": next_month(month)}}})

    runs = summarize(ledger.entries(), USER, month)["coming"]["standing_runs"]

    assert [run["standing_mandate_id"] for run in runs] == ["s3"]


def test_what_is_coming_lists_reminders_due_next_month_by_their_due_date_only():
    ledger = HashChainLedger()
    first = _note(ledger, idempotency_key="k1", reminder={"text": "Pay 999 to someone", "due": "2000-01-01"})
    month = month_of(first.ts)
    following = next_month(month)
    due_next = _note(ledger, idempotency_key="k2", reminder={"text": "Rent is due, pay 5,000 now", "due": f"{following}-28"})
    _note(ledger, idempotency_key="k3", reminder={"text": "Someday", "due": "soon"})
    _note(ledger, idempotency_key="k4", reminder={"text": "This month", "due": f"{month}-01"})

    summary = summarize(ledger.entries(), USER, month)
    text = render(summary, "en")

    assert summary["coming"]["reminders"] == [
        {"text": "Rent is due, pay 5,000 now", "due": f"{following}-28T00:00:00+00:00", "seq": due_next.seq}
    ]
    assert f"a reminder due {following}-28" in text
    assert "5,000" not in text and "999" not in text


def test_with_nothing_coming_the_note_says_nothing_is_on_file():
    text = render(summarize([], USER, "2026-09"), "en")

    assert "Coming in 2026-10: nothing on file." in text


def test_every_figure_names_its_entries_and_seqs_of_lists_all_of_them():
    s = _quoted_and_paid()
    created = _standing_note(s.ledger)

    summary = summarize(s.ledger.entries(), USER, _month_now())
    seqs = seqs_of(summary)

    execution = next(e for e in s.ledger.entries() if e.kind == "execution" and "route" in e.payload)
    quote = next(e for e in s.ledger.entries() if e.kind == "execution" and e.payload["action"]["type"] == "get_quote")
    assert {execution.seq, quote.seq, created.seq} <= set(seqs)
    assert seqs == sorted(set(seqs))


@pytest.mark.parametrize(
    ("lang", "pieces"),
    [
        ("pt", ["Custo de câmbio pago: 0 SGD em SG>BR.", "Impostos: nenhum valor de imposto está registrado",
                "Rotas usadas: 1 via wise.", "a menos que a transferência bancária cotada na mesma mensagem",
                "Fora do comum: pedidos recusados 0", "Previsto para"]),
        ("zh", ["已付汇率成本：SG>BR 上 0 SGD。", "税费：没有记录任何税费数字", "使用的路线：wise 1 笔。",
                "比同一轮对话中报价的银行电汇少花", "异常情况：被拒绝的请求 0 次", "）安排："]),
    ],
)
def test_the_new_sections_are_written_in_the_students_language(lang, pieces):
    s = _quoted_and_paid()

    text = render(summarize(s.ledger.entries(), USER, _month_now()), lang)

    for piece in pieces:
        assert piece in text


def test_next_month_wraps_the_year():
    assert next_month("2026-12") == "2027-01"
    assert next_month("2026-10") == "2026-11"


def test_the_tool_and_the_tick_carry_the_sequence_list_beside_the_text():
    ledger = HashChainLedger()
    s = _rent_paid(ledger=ledger)
    s.adapter._responses += [_call("monthly_summary", {}), _say("")]
    s.loop.handle(USER, _user("Give me this month's summary"))
    s.loop.write_monthly_notes(_first_of_next_month(_month_now()))

    tool = [e for e in ledger.entries() if e.kind == "execution" and e.payload["action"]["type"] == "monthly_summary"][-1]
    note = _monthly_notes(ledger)[0]
    assert tool.payload["result"]["seqs"] == seqs_of(tool.payload["result"]["summary"])
    assert note["seqs"] == seqs_of(note["summary"])


def test_the_tool_and_the_tick_write_the_same_text_as_the_loops_monthly_note():
    ledger = HashChainLedger()
    s = _rent_paid(ledger=ledger)
    month = _month_now()
    s.adapter._responses += [_call("monthly_summary", {}), _say("")]
    reply = s.loop.handle(USER, _user("Give me this month's summary"))

    built = s.loop.monthly_note(USER, month)
    s.loop.write_monthly_notes(_first_of_next_month(month))

    assert built["text"] in reply.text
    assert _monthly_notes(ledger)[0]["text"] == built["text"]
    assert built["month"] == month and built["lang"] == "en"
    assert built["seqs"] == seqs_of(built["summary"])
