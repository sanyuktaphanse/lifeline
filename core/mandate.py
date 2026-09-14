from collections.abc import Sequence
from datetime import date, timezone
from decimal import Decimal

from contracts.schemas import Action, ActionType, Decision, Mandate


def _utc_date(action: Action) -> date:
    return action.requested_at.astimezone(timezone.utc).date()


def _spent_on(day: date, history: Sequence[Action]) -> Decimal:
    return sum(
        (
            past.amount
            for past in history
            if past.type is ActionType.TRANSFER
            and past.amount is not None
            and _utc_date(past) == day
        ),
        Decimal(0),
    )


def check(
    action: Action, mandate: Mandate, history: Sequence[Action] = ()
) -> Decision:
    reasons: list[str] = []
    rule_ids: list[str] = []

    if action.type is ActionType.TRANSFER:
        if action.currency != mandate.currency:
            rule_ids.append("R04")
            reasons.append(
                f"Currency {action.currency} does not match the mandate currency "
                f"{mandate.currency}."
            )

        if action.payee_id not in mandate.allowed_payees:
            rule_ids.append("R06")
            reasons.append(f"Payee {action.payee_id} is not in the allowed payees.")

        if action.corridor not in mandate.allowed_corridors:
            rule_ids.append("R05")
            reasons.append(f"Corridor {action.corridor} is not in the allowed corridors.")

        if action.purpose not in mandate.allowed_purposes:
            rule_ids.append("R07")
            reasons.append(f"Purpose {action.purpose} is not in the allowed purposes.")

        if action.amount is not None and action.amount > mandate.per_txn_limit:
            rule_ids.append("R08")
            reasons.append(
                f"Amount {action.amount} is above the per transaction limit "
                f"{mandate.per_txn_limit}."
            )

        if action.amount is not None:
            running_total = _spent_on(_utc_date(action), history) + action.amount
            if running_total > mandate.daily_limit:
                rule_ids.append("R09")
                reasons.append(
                    f"Running total {running_total} for today is above the daily "
                    f"limit {mandate.daily_limit}."
                )

    return Decision(allowed=not rule_ids, reasons=reasons, rule_ids=rule_ids)
