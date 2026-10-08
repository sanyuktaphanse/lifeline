from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from contracts.interfaces import Router
from contracts.schemas import PrecheckResult, Route, RouteStatus
from rails.sim.rules import (
    CN_CDD_ENTRY,
    CN_FUNDING_ENTRY,
    CN_QUOTA_ENTRY,
    LIVING_COSTS,
    PIX_SCHEME_ENTRY,
    TUITION,
    UPI_CAP_ENTRY,
    UPI_PURPOSE_ENTRY,
    cn_documents,
    cn_purpose_refusals,
    entry,
    no_duration,
    upi_refusals,
)

# Every value below is a fixture for tests and the agent loop, not a published
# fee, rate, or rule. Source: this file. Real quotes must come from a real rail.
FIXTURE_SOURCE = "fixture"
WISE_FEE = Decimal("5.60")
BANK_WIRE_FEE = Decimal("25")
BANK_WIRE_SPREAD_PCT = Decimal("2.5")
# Fixture: the simulated UPI to PayNow route's arrival time; no entry gives one.
UPI_PAYNOW_HOURS = 1
# Fixture: a China to Singapore route is always quoted blocked, because no entry gives a duration or
# allows paying the institution; Route needs an arrival time, so zero stands for none.
CN_BLOCKED_HOURS = 0
CENT = Decimal("0.01")
# Fixture: a transfer inside Singapore to the student's own account, for a rescue's emergency
# allowance. Not a published Wise fee or arrival time.
WISE_DOMESTIC_FEE = Decimal("0")
WISE_DOMESTIC_HOURS = 1


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
                    purpose=purpose,
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
                    rule_id=PIX_SCHEME_ENTRY,
                    purpose=purpose,
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
                    purpose=purpose,
                ),
            ]
        if corridor == "SG>SG":
            return [
                self._route(
                    "wise",
                    corridor,
                    amount,
                    "SGD",
                    "SGD",
                    quoted_at,
                    fee=WISE_DOMESTIC_FEE,
                    arrival_hours=WISE_DOMESTIC_HOURS,
                    simulated=False,
                    purpose=purpose,
                )
            ]
        if corridor == "IN>SG":
            # The router knows no earlier transfer, so it checks the cap for this amount alone; the
            # rail checks the day's total when it pays.
            refusals = upi_refusals(amount, "INR", purpose, Decimal(0))
            return [
                self._route(
                    "upi_paynow_sim",
                    corridor,
                    amount,
                    "INR",
                    "SGD",
                    quoted_at,
                    arrival_hours=UPI_PAYNOW_HOURS,
                    simulated=True,
                    limit_ok=all(entry_id != UPI_CAP_ENTRY for entry_id, _ in refusals),
                    blocked_reason=" ".join(reason for _, reason in refusals) or None,
                    rule_id=refusals[0][0] if refusals else UPI_PURPOSE_ENTRY,
                    purpose=purpose,
                )
            ]
        if corridor == "CN>SG":
            refusals = cn_purpose_refusals(purpose)
            if purpose == LIVING_COSTS:
                refusals = [(CN_FUNDING_ENTRY, f"Funding the student is a remittance to their own account. {no_duration(CN_FUNDING_ENTRY)}")]
            return [
                self._route(
                    "cn_bank_remit_sim",
                    corridor,
                    amount,
                    "CNY",
                    "SGD",
                    quoted_at,
                    arrival_hours=CN_BLOCKED_HOURS,
                    simulated=True,
                    blocked_reason=" ".join(reason for _, reason in refusals),
                    rule_id=refusals[0][0] if purpose in {LIVING_COSTS, TUITION} else None,
                    purpose=purpose,
                )
            ]
        return []

    def precheck(
        self, action_kind: str, provider: str, user_context: dict[str, Any]
    ) -> PrecheckResult:
        if action_kind == "remit_from_china":
            # What the entries say the Chinese side will ask for when funding the student, and the
            # Chinese side's quota and identity rules. Nothing else, and no date.
            return PrecheckResult(
                provider=provider,
                action_kind=action_kind,
                documents_likely=cn_documents(),
                review_triggers=[
                    entry(CN_QUOTA_ENTRY)["statement"],
                    entry(CN_CDD_ENTRY)["statement"],
                    no_duration(CN_FUNDING_ENTRY),
                ],
                ready=None,
                rule_ids=[CN_FUNDING_ENTRY, CN_QUOTA_ENTRY, CN_CDD_ENTRY],
            )
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
        limit_ok: bool = True,
        purpose: str | None = None,
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
            limit_ok=limit_ok,
            blocked_reason=blocked_reason,
            rule_id=rule_id,
            rate_source=FIXTURE_SOURCE,
            quoted_at=quoted_at,
            purpose=purpose,
        )
