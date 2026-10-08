"""Stage 9, item three: reminders read from the reminder notes in the student's ledger, split at a time."""

from datetime import datetime, timedelta, timezone

import pytest

from core.ledger import HashChainLedger
from core.reminders import due_time, reminders_of, split

USER = "student_001"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-28", datetime(2026, 9, 28, tzinfo=timezone.utc)),
        ("2026-09-28T09:30:00Z", datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc)),
        ("2026-09-28T17:30:00+08:00", datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc)),
        ("2026-09-28T09:30:00", datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc)),
        ("in three days", None),
        ("２０２６-０９-２８", None),
        ("2026-02-30", None),
        ("", None),
        (None, None),
        (20260928, None),
    ],
)
def test_a_due_value_is_read_as_a_date_or_a_time_in_utc_or_has_no_due_time(value, expected):
    assert due_time(value) == expected


def _ledger():
    ledger = HashChainLedger()
    first = ledger.append("agent", "note", {"user_id": USER, "turn": 1, "reminder": {"text": "Rent", "due": "2026-09-28"}})
    ledger.append("agent", "note", {"user_id": "student_002", "turn": 1, "reminder": {"text": "Not yours", "due": "2026-09-01"}})
    ledger.append("agent", "note", {"user_id": USER, "turn": 2, "kind": "payee_added"})
    second = ledger.append("agent", "note", {"user_id": USER, "turn": 3, "reminder": {"text": "Visa", "due": "2026-10-15T08:00:00Z"}})
    third = ledger.append("agent", "note", {"user_id": USER, "turn": 4, "reminder": {"text": "Someday", "due": None}})
    return ledger, first, second, third


def test_only_the_students_own_reminder_notes_are_read_with_their_sequences():
    ledger, first, second, third = _ledger()

    assert reminders_of(ledger.entries(), USER) == [
        {"text": "Rent", "due": "2026-09-28T00:00:00+00:00", "seq": first.seq},
        {"text": "Visa", "due": "2026-10-15T08:00:00+00:00", "seq": second.seq},
        {"text": "Someday", "due": None, "seq": third.seq},
    ]


def test_due_is_at_or_before_now_and_upcoming_is_the_rest_with_no_due_time_included():
    ledger, first, second, third = _ledger()
    reminders = reminders_of(ledger.entries(), USER)

    lists = split(reminders, datetime(2026, 10, 1, tzinfo=timezone.utc))

    assert [item["seq"] for item in lists["due"]] == [first.seq]
    assert [item["seq"] for item in lists["upcoming"]] == [second.seq, third.seq]


def test_a_reminder_is_due_exactly_at_its_due_time_and_not_a_moment_before():
    ledger, _, second, _ = _ledger()
    reminders = reminders_of(ledger.entries(), USER)
    at = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)

    assert second.seq in [item["seq"] for item in split(reminders, at)["due"]]
    assert second.seq in [item["seq"] for item in split(reminders, at - timedelta(microseconds=1))["upcoming"]]
