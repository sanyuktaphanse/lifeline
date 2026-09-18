from datetime import datetime, timedelta, timezone

# Source: docs/decisions.md, 18 September 2026. A run may happen from the notice until a day after it falls due.
RUN_WINDOW_AFTER_DUE = timedelta(hours=24)


def _day(schedule: str) -> int:
    return int(schedule.removeprefix("monthly:"))


def _due(schedule: str, year: int, month: int) -> datetime:
    return datetime(year, month, _day(schedule), tzinfo=timezone.utc)


def _months_from(at: datetime) -> list[tuple[int, int]]:
    at = at.astimezone(timezone.utc)
    following = (at.year + 1, 1) if at.month == 12 else (at.year, at.month + 1)
    return [(at.year, at.month), following]


def period_of(due: datetime) -> str:
    return f"{due.year:04d}-{due.month:02d}"


def occurrence_containing(schedule: str, notice_hours: int, at: datetime) -> tuple[str, datetime] | None:
    for year, month in _months_from(at):
        due = _due(schedule, year, month)
        if due - timedelta(hours=notice_hours) <= at < due + RUN_WINDOW_AFTER_DUE:
            return period_of(due), due
    return None


def next_occurrence(schedule: str, at: datetime) -> tuple[str, datetime]:
    for year, month in _months_from(at):
        due = _due(schedule, year, month)
        if at < due + RUN_WINDOW_AFTER_DUE:
            return period_of(due), due
    raise AssertionError("One of two consecutive months always has a due date after any time in the first.")
