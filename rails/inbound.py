"""Money sent to the student, such as a parent's transfer, seeded into the rail that carries it.

A seeded receipt is not the student's payment, so it is never written to the ledger. The loop is
told which rail holds each one, so the student can trace it. Source: docs/decisions.md, 8 October 2026.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from contracts.interfaces import Rail
from contracts.schemas import Receipt, RouteStatus, Route


@dataclass(frozen=True)
class Inbound:
    """One transfer sent to the student: its receipt, and the route it came over."""

    receipt: Receipt
    route: Route


def inbound_from_fixture(
    block: Mapping[str, list[Mapping[str, Any]]] | None, rails: Mapping[str, Rail]
) -> dict[str, list[Inbound]]:
    """Turn a fixture's `inbound_receipts`, a rail key to a list of transfers, into inbound receipts per rail."""
    now = datetime.now(timezone.utc)
    inbound: dict[str, list[Inbound]] = {}
    for key, transfers in (block or {}).items():
        if key not in rails:
            raise ValueError(f"inbound_receipts names {key}, which is not among the rails built: {sorted(rails)}")
        rail = rails[key]
        for transfer in transfers:
            sent = now - timedelta(hours=float(transfer["sent_hours_ago"]))
            amount = Decimal(str(transfer["amount"]))
            receipt = Receipt(
                receipt_id=transfer["receipt_id"],
                rail=rail.name,
                amount=amount,
                currency=transfer["currency"],
                status=transfer["status"],
                stage_entered_at=sent,
                mandate_ref=f"inbound:{transfer['sender']}",
                idempotency_key=f"inbound:{transfer['receipt_id']}",
                simulated=rail.simulated,
                executed_at=sent,
            )
            # Fixture: Lifeline never quoted an inbound transfer, so its route carries no fee and no
            # arrival time of its own; the rail keeps it only as the request the receipt answered.
            route = Route(
                rail=rail.name,
                corridor=transfer["corridor"],
                amount=amount,
                currency_from=transfer["currency"],
                currency_to=transfer["currency"],
                fee=Decimal(0),
                spread_cost=Decimal(0),
                tax_lines=[],
                arrival_hours=0,
                status=RouteStatus.SIMULATED if rail.simulated else RouteStatus.UP,
                simulated=rail.simulated,
                limit_ok=True,
                quoted_at=sent,
            )
            inbound.setdefault(key, []).append(Inbound(receipt, route))
    return inbound


def seed_inbound(rails: Mapping[str, Any], inbound: Mapping[str, list[Inbound]]) -> dict[str, str]:
    """Give each rail its inbound receipts through its `restore`, and say which rail holds each id."""
    where: dict[str, str] = {}
    for key, transfers in inbound.items():
        for transfer in transfers:
            rails[key].restore(transfer.receipt, transfer.route, transfer.receipt.mandate_ref)
            where[transfer.receipt.receipt_id] = key
    return where
