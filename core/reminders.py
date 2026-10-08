"""The reminders a student set, read from the reminder notes in their ledger and nothing else.

A reminder note is what set_reminder writes: its text and its due value as the tool was given them. A due
value written as a date is due at the start of that day in UTC, and one written as a time without a zone
is read in UTC. A due value that is neither has no due time. Nothing here marks a reminder delivered,
because the app delivers it. Source: docs/decisions.md, 8 October 2026.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime, time, timezone
from typing import Any

from contracts.schemas import LedgerEntry

# ASCII digits only, as a month in the monthly note is, so a date in fullwidth digits is not read as one.
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
DATE_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+(?:Z|[+-][0-9]{2}:?[0-9]{2})?")


def due_time(value: Any) -> datetime | None:
    """When a reminder falls due, in UTC, or None when its due value is not a date or a time."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        if DATE.fullmatch(text):
            return datetime.combine(date.fromisoformat(text), time(), tzinfo=timezone.utc)
        if DATE_TIME.fullmatch(text):
            moment = datetime.fromisoformat(text)
            return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:
        return None
    return None


def reminders_of(entries: Iterable[LedgerEntry], user_id: str) -> list[dict[str, Any]]:
    """Every reminder the student set, in ledger order, with its text, its due time and the note's sequence."""
    found = []
    for entry in entries:
        payload = entry.payload
        reminder = payload.get("reminder")
        if entry.kind != "note" or payload.get("user_id") != user_id or not isinstance(reminder, dict):
            continue
        due = due_time(reminder.get("due"))
        found.append({"text": str(reminder.get("text", "")), "due": due.isoformat() if due else None, "seq": entry.seq})
    return found


def split(reminders: list[dict[str, Any]], now: datetime) -> dict[str, list[dict[str, Any]]]:
    """Due: a due time at or before now. Upcoming: the rest, a reminder with no due time included."""
    due = [item for item in reminders if item["due"] is not None and datetime.fromisoformat(item["due"]) <= now]
    seqs = {item["seq"] for item in due}
    return {"due": due, "upcoming": [item for item in reminders if item["seq"] not in seqs]}
