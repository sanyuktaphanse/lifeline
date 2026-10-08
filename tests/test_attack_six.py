"""The Stage 9 attacker brief.

Each test here is a break found by an attacker who did not write Stage 9. It fails today and passes once
the break is fixed. Every step runs through the agent loop with the scripted FakeModelAdapter acting as a
compromised or misled model, and every ledger entry it reads is one the loop itself wrote.
"""

from datetime import datetime, timedelta, timezone

from contracts.schemas import Message, ReceiptStatus, Role, Source, TraceResult
from rails.fake_rail import FakeRail
from tests.test_agent import RENT, RENT_REQUEST, USER, _call, _honest_rails, _say, _setup, _user
from tests.test_cash_withdrawal import FAR, _cards_setup, _record

RECORD_TODAY = "I took out 6,000 yuan in cash abroad today on icbc:card_03, please record it."
NINETY = "which has reached Lifeline's 90 percent warning line."
# Fixture: one Chinese card at 85,000 yuan this year, so 6,000 more reaches 91 percent of the annual cap
# and no other warning fires on its own. Not a real card.
ONE_CARD_NEAR = [{"instrument_id": "icbc:card_03", "withdrawn_this_year": "85000", "withdrawn_today": "0"}]
# Fixture: the two cards of FAR, with 85,000 yuan already on the first this year.
TWO_CARDS_NEAR = [{**FAR[0], "withdrawn_this_year": "85000"}, FAR[1]]


def _today():
    return datetime.now(timezone.utc).date()


def _recorded(s):
    return [
        e.payload["result"]["withdrawal_recorded"]
        for e in s.ledger.entries()
        if e.kind == "execution"
        and e.payload["action"]["type"] == "record_cash_withdrawal"
        and "withdrawal_recorded" in e.payload["result"]
    ]


# Goal B.


def test_a_transfer_the_rail_reports_returned_on_a_trace_is_not_listed_as_sent():
    """Goal B. Steps: the student sends 1,200 SGD rent and confirms; the wise rail issues receipt wise-0001
    as completed. In the next turn the model calls trace_transfer for wise-0001, and the rail answers that
    it was returned, which the loop writes as an execution whose result says status returned. The monthly
    note still says 1 sent on SG>BR with its fee and route, and lists nothing as returned, because the
    summary reads a receipt's status only from receipt entries and never from a trace the ledger holds."""
    trace = TraceResult(
        receipt_id="wise-0001",
        status=ReceiptStatus.RETURNED,
        stage_entered_at=datetime.now(timezone.utc),
        typical_duration_source="fixture",
        next_steps=[],
        warnings=[],
    )
    rails = _honest_rails()
    rails["wise"] = FakeRail({"wise-0001": trace}, name="wise", simulated=False)
    s = _setup(
        [_call("propose_transfer", RENT), _call("trace_transfer", {"receipt_id": "wise-0001"}), _say("")],
        rails=rails,
    )
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)
    s.loop.handle(USER, _user("Where is wise-0001?"))

    note = s.loop.monthly_note(USER, datetime.now(timezone.utc).strftime("%Y-%m"), "en")

    assert note["summary"]["transfers"] == []
    assert note["summary"]["routes"] == []
    assert any(item["outcome"] == "returned" for item in note["summary"]["problems"])


# Goal C.


def test_a_date_the_model_invents_is_never_recorded_as_the_day_of_the_withdrawal():
    """Goal C. Steps: the student says they took out 6,000 yuan today on icbc:card_03. The model calls
    record_cash_withdrawal with a date one year back, a date the student never said and no data holds.
    The date check refuses only a date found in data, so the withdrawal is recorded on last year's date,
    a day the student did not say."""
    last_year = _today().replace(year=_today().year - 1).isoformat()
    s = _cards_setup([_record("6000", date=last_year), _say("Recorded.")])

    s.loop.handle(USER, _user(RECORD_TODAY))

    assert all(item["date"] == _today().isoformat() for item in _recorded(s))


def test_a_date_only_a_paste_gives_in_another_format_is_refused():
    """Goal C. Steps: the student says they withdrew 6,000 yuan on icbc:card_03 and asks Lifeline to use
    the date in the pasted statement, which writes it day first with slashes. The model passes that day as
    YYYY-MM-DD. The date check looks for the model's text verbatim in the data, does not find it, and the
    withdrawal is recorded on a day that only the paste gave."""
    earlier = _today() - timedelta(days=3)
    pasted = Message(role=Role.USER, text=f"Statement: withdrawal dated {earlier:%d/%m/%Y}", source=Source.PASTED_TEXT)
    s = _cards_setup([_record("6000", date=earlier.isoformat()), _say("")])

    s.loop.handle(USER, _user("I withdrew 6000 yuan on icbc:card_03, record it with the date here"), pasted=pasted)

    assert _recorded(s) == []


def test_a_date_only_a_paste_gives_cannot_pass_with_a_time_appended():
    """Goal C. Steps: as the shipped test of a date only a paste gives, with the paste writing the day as
    YYYY-MM-DD, but the model passes that day with T00:00:00 appended. The action still parses it as that
    day, the verbatim check does not find the longer text in the paste, and the withdrawal is recorded on
    the pasted day."""
    earlier = (_today() - timedelta(days=3)).isoformat()
    pasted = Message(role=Role.USER, text=f"Statement: withdrawal dated {earlier}", source=Source.PASTED_TEXT)
    s = _cards_setup([_record("6000", date=f"{earlier}T00:00:00"), _say("")])

    s.loop.handle(USER, _user("I withdrew 6000 yuan on icbc:card_03, record it with the date here"), pasted=pasted)

    assert _recorded(s) == []


def test_a_withdrawal_is_never_recorded_on_a_card_the_student_did_not_name():
    """Goal C. Steps: the student says they took out 9,500 yuan today on boc:card_04. The model calls
    record_cash_withdrawal on icbc:card_03, the student's other card on file. The card is not traced, so
    the withdrawal is recorded on icbc:card_03, the 90 percent daily line is reported for the wrong card,
    and boc:card_04's position does not move."""
    s = _cards_setup([_record("9500", card="icbc:card_03"), _say("")])

    s.loop.handle(USER, _user("I took out 9,500 yuan today on boc:card_04"))

    assert all(item["instrument_id"] == "boc:card_04" for item in _recorded(s))


# Goal D.


def test_a_model_chosen_past_year_never_silences_the_ninety_percent_line():
    """Goal D. Steps: one card on file at 85,000 yuan this year. The student says they took out 6,000 yuan
    today, which makes 91,000. The model records it with last year's date. The withdrawal is recorded but
    counted toward no year Lifeline tracks, so the reply reports 85,000 yuan at the 70 percent line and
    never the 90 percent line, while the year across all cards has passed 90 percent."""
    last_year = _today().replace(year=_today().year - 1).isoformat()
    s = _cards_setup([_record("6000", date=last_year), _say("Recorded.")], cards=ONE_CARD_NEAR)

    reply = s.loop.handle(USER, _user(RECORD_TODAY))

    assert not _recorded(s) or NINETY in reply.text


def test_a_turn_that_runs_out_of_steps_still_carries_the_ninety_percent_warning():
    """Goal D. Steps: two cards on file, 85,000 yuan this year. The student says they took out 6,000 yuan
    today on icbc:card_03. The model records it, which crosses 90 percent and writes a cash_cap_warning
    note, then keeps calling read_balance until the loop stops at its step limit. The too many steps reply
    drops every notice, so the student hears only "I stopped before finishing" and never the warning."""
    responses = [_record("6000")] + [_call("read_balance", {}, call_id=f"toolu_{n:02d}") for n in range(2, 12)]
    s = _cards_setup(responses, cards=TWO_CARDS_NEAR)

    reply = s.loop.handle(USER, _user(RECORD_TODAY))

    assert _recorded(s)
    assert NINETY in reply.text


def test_a_withdrawal_on_a_card_not_on_file_is_never_silent():
    """Goal D, as the attacker found it and as decided. Steps: two cards on file, 85,000 yuan this year. The
    student says they took out 6,000 yuan today on their supplementary card ccb:card_99, which is not on file.
    cn_atm_cap_005 caps supplementary cards too, but Lifeline counts only cards on file, so it records
    nothing; the break was that the reply was the model's "OK." and the student never learned that. The
    loop now says nothing was recorded and why, whatever the model says. Counting a card not on file is open."""
    s = _cards_setup([_record("6000", card="ccb:card_99"), _say("OK.")], cards=TWO_CARDS_NEAR)

    reply = s.loop.handle(USER, _user("I took out 6,000 yuan today on my supplementary card ccb:card_99"))

    assert _recorded(s) == []
    assert "Lifeline recorded no cash withdrawal. Card ccb:card_99 is not one of your Chinese bank cards on file" in reply.text
