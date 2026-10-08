import hashlib
import hmac
import json
import os
from collections.abc import Sequence
from datetime import date, timedelta, timezone
from decimal import Decimal

from contracts.interfaces import MandateEngine
from contracts.schemas import Action, ActionType, Decision, Mandate, Source, StandingMandate, Tier
from core.standing import occurrence_containing
from core.tiers import TIERS

DEVELOPMENT_CONFIRM_SECRET = "lifeline-development-secret-not-for-production"
TRANSFER_WARNING_KEY = "warn.transfer.irreversible"
# Source: project decision of 18 September 2026. Every T2 action needs the
# confirmation round trip, and each type carries its own warning for the student.
WARNING_KEYS = {
    ActionType.TRANSFER: TRANSFER_WARNING_KEY,
    ActionType.ADD_PAYEE: "warn.payee.new",
    ActionType.FREEZE_CARD: "warn.freeze.card",
    ActionType.CREATE_STANDING_MANDATE: "warn.standing.new",
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
            action.standing_mandate_id or "",
            action.standing_terms.model_dump_json() if action.standing_terms else "",
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


def _standing_named(action: Action, mandate: Mandate) -> StandingMandate | None:
    return next((s for s in mandate.standing_mandates if s.id == action.standing_mandate_id), None)


def _confirmed_standing(action: Action, mandate: Mandate) -> StandingMandate | None:
    standing = _standing_named(action, mandate)
    if standing is None or standing.confirmed_at > action.requested_at:
        return None
    return standing


def _outside_pattern(action: Action, mandate: Mandate, history: Sequence[Action]) -> list[str]:
    standing = _standing_named(action, mandate)
    if standing is None:
        return [f"no standing mandate {action.standing_mandate_id} is on mandate {mandate.id}"]
    if not standing.active:
        return []
    if standing.confirmed_at > action.requested_at:
        return [f"standing mandate {standing.id} was confirmed after this request"]
    outside = []
    for name, value, expected in (
        ("payee", action.payee_id, standing.payee_id),
        ("corridor", action.corridor, standing.corridor),
        ("purpose", action.purpose, standing.purpose),
    ):
        if value != expected:
            outside.append(f"the {name} {value} is not {expected}")
    allowed_drift = standing.amount * standing.tolerance_pct / 100
    if action.amount is None or abs(action.amount - standing.amount) > allowed_drift:
        outside.append(
            f"the amount {action.amount} is more than {standing.tolerance_pct} percent "
            f"from {standing.amount}"
        )
    occurrence = occurrence_containing(standing.schedule, standing.notice_hours, action.requested_at)
    if occurrence is None:
        outside.append(
            f"it was requested at {action.requested_at.astimezone(timezone.utc).isoformat(timespec='seconds')}, "
            f"outside the window of schedule {standing.schedule}"
        )
    elif any(
        past.type is ActionType.TRANSFER
        and past.standing_mandate_id == standing.id
        and occurrence_containing(standing.schedule, standing.notice_hours, past.requested_at) == occurrence
        for past in history
    ):
        outside.append(f"a run for {occurrence[0]} already executed")
    return outside


class DeterministicMandateEngine(MandateEngine):
    def confirmation_token_for(self, action: Action, mandate: Mandate) -> str:
        return confirmation_token_for(action, mandate)

    def check(
        self, action: Action, mandate: Mandate, history: Sequence[Action] = ()
    ) -> Decision:
        tier = TIERS[action.type]
        standing_run = action.type is ActionType.TRANSFER and action.standing_mandate_id is not None
        trusted_source = action.source is Source.USER_TURN or (
            action.source is Source.STANDING_MANDATE
            and standing_run
            and _confirmed_standing(action, mandate) is not None
        )

        if not trusted_source:
            return Decision(
                allowed=False,
                reasons=[
                    f"This action came from {action.source.value}, which is data and "
                    "never an instruction. Only the user's own turn can ask for an action."
                ],
                rule_ids=["R01"],
                tier=tier,
            )

        named = _standing_named(action, mandate) if standing_run else None
        inactive = named is not None and not named.active
        outside = _outside_pattern(action, mandate, history) if standing_run else []
        within_pattern = standing_run and not outside and not inactive
        if within_pattern:
            tier = Tier.T1
        escalation = (
            (["R13"], [f"This transfer falls outside standing mandate {action.standing_mandate_id} because "
                       + ", and ".join(outside) + "."])
            if outside
            else ([], [])
        )

        reasons: list[str] = []
        rule_ids: list[str] = []

        if inactive:
            rule_ids.append("R12")
            reasons.append(
                f"Standing mandate {action.standing_mandate_id} is inactive, so no run may be made under it."
            )

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

        if action.type is ActionType.FREEZE_CARD and not action.instrument_id:
            rule_ids.append("R04")
            reasons.append("Freezing a card needs the card's instrument id, and this one has none.")

        if action.type is ActionType.REROUTE_TO_BACKUP and not action.instrument_id:
            rule_ids.append("R04")
            reasons.append("Rerouting to a backup needs the backup's instrument id, and this one has none.")

        if action.type is ActionType.CREATE_STANDING_MANDATE:
            missing = [
                name
                for name in ("amount", "currency", "corridor", "payee_id", "purpose", "standing_mandate_id", "standing_terms")
                if getattr(action, name) in (None, "")
            ]
            if missing:
                rule_ids.append("R04")
                reasons.append(
                    "A standing mandate needs an amount, a currency, a corridor, a payee, a purpose, "
                    f"an id, and its terms, and this one has no {', no '.join(missing)}."
                )

        standing_actions = (ActionType.CANCEL_STANDING_RUN, ActionType.DEACTIVATE_STANDING_MANDATE)
        if action.type in standing_actions and _standing_named(action, mandate) is None:
            rule_ids.append("R04")
            reasons.append(
                f"{action.type.value} needs a standing mandate on mandate {mandate.id}, and "
                f"{action.standing_mandate_id or 'none'} is not one."
            )

        if any(past.idempotency_key == action.idempotency_key for past in history):
            return Decision(
                allowed=False,
                reasons=[f"Idempotency key {action.idempotency_key} was already executed."],
                rule_ids=["R10"],
                tier=tier,
            )

        if action.type in (ActionType.TRANSFER, ActionType.CREATE_STANDING_MANDATE):
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
            if (missing or action.currency != mandate.currency) and "R04" not in rule_ids:
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

            if action.type is ActionType.TRANSFER and action.amount is not None:
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

        escalation_ids, escalation_reasons = escalation
        if rule_ids:
            return Decision(
                allowed=False,
                reasons=escalation_reasons + reasons,
                rule_ids=escalation_ids + rule_ids,
                tier=tier,
            )

        confirms = tier is Tier.T2
        needs_token = confirms and action.confirmation_token is None

        return Decision(
            allowed=True,
            reasons=escalation_reasons,
            rule_ids=escalation_ids + (["R12"] if within_pattern else [ALLOWED_RULE[tier]]),
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
