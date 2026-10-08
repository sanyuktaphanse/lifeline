"""Simulated UPI to PayNow, India to Singapore, person to person.

Its purposes come from in_upi_paynow_purpose_001 and its daily cap from in_upi_paynow_cap_002, by id.
Source: docs/decisions.md, 8 October 2026.
"""

import re
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from contracts.schemas import ReceiptStatus, Route
from rails.sim.base import SimRail
from rails.sim.rules import UPI_CAP_ENTRY, upi_refusals


# The remitter is in India, as in_upi_paynow_purpose_001 says, so the cap's "day" is India's day.
# The zone comes from the time zone database, not a figure written here.
SENDER_ZONE = ZoneInfo("Asia/Kolkata")
# A mandate's versions share a sender: mandate-parent-v1 and mandate-parent-v2 are one parent.
VERSION = re.compile(r"-v\d+$")


def _sender(mandate_ref: str) -> str:
    return VERSION.sub("", mandate_ref)


class UpiPayNowSimRail(SimRail):
    NAME = "upi_paynow_sim"
    STAGES = (("created", ReceiptStatus.CREATED), ("completed", ReceiptStatus.COMPLETED))
    # Fixture: one simulated hour from created to completed; the RBI entry gives no duration.
    STAGE_HOURS = 1
    DURATION_ENTRY = UPI_CAP_ENTRY

    def refusals(self, route: Route, mandate_ref: str) -> list[str]:
        day = datetime.now(timezone.utc).astimezone(SENDER_ZONE).date()
        today = [
            receipt.amount
            for receipt in self._receipts.values()
            if _sender(receipt.mandate_ref) == _sender(mandate_ref)
            and receipt.executed_at.astimezone(SENDER_ZONE).date() == day
            # A transfer the student cancelled keeps its share of the day, as it keeps its share of the
            # mandate's daily limit; only one the provider returned frees it. Source: docs/decisions.md.
            and (receipt.status is not ReceiptStatus.RETURNED or receipt.receipt_id in self._cancelled)
        ]
        earlier = sum(today, Decimal(0))
        return [reason for _, reason in upi_refusals(route.amount, route.currency_from, route.purpose, earlier)]
