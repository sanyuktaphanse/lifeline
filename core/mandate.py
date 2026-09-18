import hashlib
import hmac
import json
import os
from collections.abc import Sequence
from datetime import date, timedelta, timezone
from decimal import Decimal

from contracts.interfaces import MandateEngine
from contracts.schemas import Action, ActionType, Decision, Mandate, Source, Tier
from core.tiers import TIERS

DEVELOPMENT_CONFIRM_SECRET = "lifeline-development-secret-not-for-production"
TRANSFER_WARNING_KEY = "warn.transfer.irreversible"
# Source: project decision of 18 September 2026. Every T2 action needs the
# confirmation round trip, and each type carries its own warning for the student.
WARNING_KEYS = {
    ActionType.TRANSFER: TRANSFER_WARNING_KEY,
    ActionType.ADD_PAYEE: "warn.payee.new",
    ActionType.FREEZE_CARD: "warn.freeze.card",
}
# Source: the order of evaluation table in docs/technical-reference.md. An allowed
# T0 or T1 action is governed by the tier rule R02; an allowed T2 action by the
# confirmation rule R11, before and after the student confirms.
ALLOWED_RULE = {Tier.T0: "R02", Tier.T1: "R02", Tier.T2: "R11"}


def _confirm_secret() -> bytes:
    secret = os.environ.get("LIFELINE_CONFIRM_SECRET")
    if secret is None:
        if os.environ.get("LIFELINE_ENV") == "production":
            raise RuntimeError(
                "LIFELINE_CONFIRM_SECRET must be set when LIFELINE_ENV is production."
            )
        secret = DEVELOPMENT_CONFIRM_SECRET
    return secret.encode("utf-8")


def _amount_field(amount: Decimal | None) -> str:
    if amount is None:
        return ""
    return format(amount.normalize(), "f")


def confirmation_token_for(action: Action, mandate: Mandate) -> str:
    payload = json.dumps(
        [
            mandate.user_id,
            action.type.value,
            action.idempotency_key,
            _amount_field(action.amount),
            action.currency or "",
            action.corridor or "",
            action.payee_id or "",
            action.purpose or "",
            action.instrument_id or "",
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hmac.new(
        _confirm_secret(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


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


class DeterministicMandateEngine(MandateEngine):
    def confirmation_token_for(self, action: Action, mandate: Mandate) -> str:
        return confirmation_token_for(action, mandate)

    def check(
        self, action: Action, mandate: Mandate, history: Sequence[Action] = ()
    ) -> Decision:
        tier = TIERS[action.type]

        if action.source is not Source.USER_TURN:
            return Decision(
                allowed=False,
                reasons=[
                    f"This action came from {action.source.value}, which is data and "
                    "never an instruction. Only the user's own turn can ask for an action."
                ],
                rule_ids=["R01"],
                tier=tier,
            )

        reasons: list[str] = []
        rule_ids: list[str] = []

        if tier is Tier.T3:
            rule_ids.append("R02")
            reasons.append(
                f"Action {action.type.value} is tier T3 and a mandate cannot authorise it. "
                "The user has to approve it directly."
            )

        if tier is not Tier.T0 and not (
            mandate.valid_from <= action.requested_at <= mandate.valid_until
        ):
            rule_ids.append("R03")
            reasons.append(
                f"The mandate is valid from {mandate.valid_from} until "
                f"{mandate.valid_until} and this action was requested at "
                f"{action.requested_at}."
            )

        if action.type is ActionType.ADD_PAYEE and not action.payee_id:
            rule_ids.append("R04")
            reasons.append("Adding a payee needs a payee id, and this one has none.")

        if action.type is ActionType.TRANSFER:
            if any(past.idempotency_key == action.idempotency_key for past in history):
                return Decision(
                    allowed=False,
                    reasons=[
                        f"Idempotency key {action.idempotency_key} was already executed."
                    ],
                    rule_ids=["R10"],
                    tier=tier,
                )

            missing = [
                name
                for name, value in (("amount", action.amount), ("currency", action.currency))
                if value is None
            ]
            if missing:
                reasons.append(
                    "A transfer needs an amount and a currency, and this one has "
                    + " and ".join(f"no {name}" for name in missing)
                    + "."
                )
            elif action.currency != mandate.currency:
                reasons.append(
                    f"Currency {action.currency} does not match the mandate currency "
                    f"{mandate.currency}."
                )
            if missing or action.currency != mandate.currency:
                rule_ids.append("R04")

            if action.payee_id not in mandate.allowed_payees:
                rule_ids.append("R06")
                reasons.append(f"Payee {action.payee_id} is not in the allowed payees.")

            added_at = mandate.payee_added_at.get(action.payee_id or "")
            if added_at is not None:
                allowed_from = added_at + timedelta(hours=mandate.cooling_hours)
                if action.requested_at < allowed_from:
                    rule_ids.append("R14")
                    reasons.append(
                        f"Payee {action.payee_id} was added less than "
                        f"{mandate.cooling_hours} hours ago and can receive transfers from "
                        f"{allowed_from.astimezone(timezone.utc).isoformat(timespec='seconds')}."
                    )

            if action.corridor not in mandate.allowed_corridors:
                rule_ids.append("R05")
                reasons.append(
                    f"Corridor {action.corridor} is not in the allowed corridors."
                )

            if action.purpose not in mandate.allowed_purposes:
                rule_ids.append("R07")
                reasons.append(
                    f"Purpose {action.purpose} is not in the allowed purposes."
                )

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

        if (
            tier is Tier.T2
            and action.confirmation_token is not None
            and not hmac.compare_digest(
                action.confirmation_token, self.confirmation_token_for(action, mandate)
            )
        ):
            rule_ids.append("R11")
            reasons.append("The confirmation token does not belong to this exact action.")

        if rule_ids:
            return Decision(allowed=False, reasons=reasons, rule_ids=rule_ids, tier=tier)

        confirms = tier is Tier.T2
        needs_token = confirms and action.confirmation_token is None

        return Decision(
            allowed=True,
            reasons=[],
            rule_ids=[ALLOWED_RULE[tier]],
            tier=tier,
            requires_confirmation=needs_token,
            warning_key=WARNING_KEYS[action.type] if confirms else None,
            confirmation_token=(
                self.confirmation_token_for(action, mandate) if needs_token else None
            ),
        )


_ENGINE = DeterministicMandateEngine()


def check(
    action: Action, mandate: Mandate, history: Sequence[Action] = ()
) -> Decision:
    return _ENGINE.check(action, mandate, history)
