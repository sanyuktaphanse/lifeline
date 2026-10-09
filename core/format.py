"""The one place an amount or a date becomes text for a student.

Every student facing sentence takes its amounts from format_amount and its dates from format_date, and fills
its template through fill, which refuses a Decimal, a float or a date that did not go through them.

Both functions return one plain form in every language today: an amount as its digits with a point before
any decimals, followed by its currency code, and a date as ISO 8601. Locale separators, such as 1.400,00 in
Portuguese, and date orders are the app's job on display, and the API returns this one plain form so the
app can parse it. The lang argument is taken now so a locale aware version changes this module and nothing
that calls it. Source: docs/decisions.md, 9 October 2026, and open item 155 in docs/technical-reference.md.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

# The values a sentence may not take as they are: each has more than one way of being written.
UNFORMATTED = (Decimal, float, date)


def format_amount(amount: Decimal | int | str, currency: str | None, lang: str, *, grouped: bool = False) -> str:
    """An amount and its currency code as one phrase, such as 1200 SGD, or the bare figure with no currency.

    grouped puts a comma every three digits, as the cash cap sentences have always written their figures.
    An amount is written out in full, never with an exponent.
    """
    value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    figure = format(value, ",f" if grouped else "f")
    return f"{figure} {currency}" if currency else figure


def format_date(moment: date | datetime, lang: str) -> str:
    """A date as YYYY-MM-DD, and a moment as ISO 8601 to the second with its offset."""
    if isinstance(moment, datetime):
        return moment.isoformat(timespec="seconds")
    return moment.isoformat()


def fill(template: str, **values: Any) -> str:
    """A template with its values, refusing any amount or date that did not go through the two functions above."""
    loose = sorted(name for name, value in values.items() if isinstance(value, UNFORMATTED))
    if loose:
        raise TypeError(f"Format these with format_amount or format_date first: {', '.join(loose)}.")
    return template.format(**values)
