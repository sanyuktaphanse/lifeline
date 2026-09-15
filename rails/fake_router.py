from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from contracts.interfaces import Router
from contracts.schemas import PrecheckResult, Route, RouteStatus

# Every value below is a fixture for tests and the agent loop, not a published
# fee, rate, or rule. Source: this file. Real quotes must come from a real rail.
FIXTURE_SOURCE = "fixture"
WISE_FEE = Decimal("5.60")
BANK_WIRE_FEE = Decimal("25")
BANK_WIRE_SPREAD_PCT = Decimal("2.5")
UPI_PAYNOW_PURPOSES = frozenset({"allowance", "family_support"})
# Fake: written in the knowledge base id style, but no such entry exists in rails/knowledge/.
FAKE_UPI_PAYNOW_PURPOSE_RULE = "in_upi_paynow_purpose_001"
CENT = Decimal("0.01")


class FakeRouter(Router):
    def quote(
        self, corridor: str, amount: Decimal, purpose: str, urgency: str
    ) -> list[Route]:
        quoted_at = datetime.now(timezone.utc)
        if corridor == "SG>BR":
            return [
                self._route(
                    "wise",
                    corridor,
                    amount,
                    "SGD",
                    "BRL",
                    quoted_at,
                    fee=WISE_FEE,
                    arrival_hours=24,
                    simulated=False,
                ),
                self._route(
                    "sim_pix",
                    corridor,
                    amount,
                    "SGD",
                    "BRL",
                    quoted_at,
                    arrival_hours=1,
                    simulated=True,
                ),
                self._route(
                    "bank_wire",
                    corridor,
                    amount,
                    "SGD",
                    "BRL",
                    quoted_at,
                    fee=BANK_WIRE_FEE,
                    spread_cost=(amount * BANK_WIRE_SPREAD_PCT / 100).quantize(CENT),
                    arrival_hours=72,
                    simulated=False,
                ),
            ]
        if corridor == "IN>SG":
            blocked = purpose not in UPI_PAYNOW_PURPOSES
            return [
                self._route(
                    "upi_paynow",
                    corridor,
                    amount,
                    "INR",
                    "SGD",
                    quoted_at,
                    arrival_hours=1,
                    simulated=True,
                    blocked_reason=(
                        f"UPI to PayNow only carries allowance or family_support, not {purpose!r}."
                        if blocked
                        else None
                    ),
                    rule_id=FAKE_UPI_PAYNOW_PURPOSE_RULE if blocked else None,
                )
            ]
        return []

    def precheck(
        self, action_kind: str, provider: str, user_context: dict[str, Any]
    ) -> PrecheckResult:
        if action_kind != "enable_pix":
            return PrecheckResult(
                provider=provider,
                action_kind=action_kind,
                documents_likely=[],
                review_triggers=[],
                ready=None,
                rule_ids=[],
            )
        return PrecheckResult(
            provider=provider,
            action_kind=action_kind,
            documents_likely=["passport", "CPF number"],
            review_triggers=["first Pix key registered on a foreign passport"],
            ready=None,
            rule_ids=[],
        )

    @staticmethod
    def _route(
        rail: str,
        corridor: str,
        amount: Decimal,
        currency_from: str,
        currency_to: str,
        quoted_at: datetime,
        *,
        arrival_hours: float,
        simulated: bool,
        fee: Decimal = Decimal("0"),
        spread_cost: Decimal = Decimal("0"),
        blocked_reason: str | None = None,
        rule_id: str | None = None,
    ) -> Route:
        return Route(
            rail=rail,
            corridor=corridor,
            amount=amount,
            currency_from=currency_from,
            currency_to=currency_to,
            fee=fee,
            spread_cost=spread_cost,
            tax_lines=[],
            arrival_hours=arrival_hours,
            status=RouteStatus.UP,
            simulated=simulated,
            limit_ok=True,
            blocked_reason=blocked_reason,
            rule_id=rule_id,
            rate_source=FIXTURE_SOURCE,
            quoted_at=quoted_at,
        )
