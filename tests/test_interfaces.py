import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.interfaces import (
    Anchor,
    Council,
    Ledger,
    MandateEngine,
    ModelAdapter,
    Rail,
    Router,
    Translator,
)
from contracts.schemas import Action, ActionType, FreezeResult, Mandate
from core.mandate import DeterministicMandateEngine, check, confirmation_token_for
from core.tiers import TIERS

FROZEN_INTERFACES = {
    MandateEngine: {"check", "confirmation_token_for"},
    Ledger: {"append", "verify", "entries", "head"},
    Anchor: {"anchor", "verify"},
    Router: {"quote", "precheck"},
    Rail: {"name", "simulated", "execute", "status", "freeze", "cancel"},
    Council: {"deliberate"},
    ModelAdapter: {"complete"},
    Translator: {"explain"},
}


def _mandate() -> Mandate:
    now = datetime.now(timezone.utc)
    return Mandate(
        id="mandate-student_001-v1",
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
        valid_from=now - timedelta(days=30),
        valid_until=now + timedelta(days=30),
    )


def _rent() -> Action:
    return Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0700-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )


@pytest.mark.parametrize("interface", FROZEN_INTERFACES)
def test_interface_declares_exactly_its_frozen_members(interface):
    assert inspect.isabstract(interface)
    assert set(interface.__abstractmethods__) == FROZEN_INTERFACES[interface]
    with pytest.raises(TypeError):
        interface()


def test_rail_execute_takes_an_idempotency_key_and_freeze_returns_a_result():
    parameters = list(inspect.signature(Rail.execute).parameters)

    assert parameters == [
        "self",
        "route",
        "mandate_ref",
        "idempotency_key",
        "confirmation_token",
    ]
    assert inspect.signature(Rail.freeze).return_annotation is FreezeResult


def test_deterministic_engine_implements_the_mandate_engine():
    engine = DeterministicMandateEngine()

    assert isinstance(engine, MandateEngine)
    assert not inspect.isabstract(DeterministicMandateEngine)


def test_engine_and_check_wrapper_give_the_same_decision():
    engine = DeterministicMandateEngine()
    mandate = _mandate()
    action = _rent()

    decision = engine.check(action, mandate)

    assert decision == check(action, mandate)
    assert decision.allowed is True
    assert decision.confirmation_token == engine.confirmation_token_for(action, mandate)
    assert engine.confirmation_token_for(action, mandate) == confirmation_token_for(
        action, mandate
    )


# Pinned so that adding or retiering an action type is a change someone has to make here on purpose.
# Source: docs/decisions.md, 18 September 2026 and 8 October 2026, the second record of which adds update_plan.
FROZEN_ACTION_TIERS = {
    "transfer": "T2",
    "read_balance": "T0",
    "set_reminder": "T1",
    "add_payee": "T2",
    "freeze_card": "T2",
    "change_limit": "T3",
    "change_mandate": "T3",
    "export_credentials": "T3",
    "trace_transfer": "T0",
    "precheck": "T0",
    "get_quote": "T0",
    "create_standing_mandate": "T2",
    "cancel_standing_run": "T1",
    "deactivate_standing_mandate": "T1",
    "rescue_identity_check": "T1",
    "check_wallet_token": "T0",
    "reroute_to_backup": "T1",
    "notify_family": "T1",
    "verify_ledger": "T0",
    "update_plan": "T1",
    "cancel_transfer": "T2",
}


def test_action_types_and_their_tiers_are_pinned():
    assert {kind.value: tier.value for kind, tier in TIERS.items()} == FROZEN_ACTION_TIERS
    assert [kind.value for kind in ActionType] == list(FROZEN_ACTION_TIERS)


def test_route_and_trace_result_carry_the_pinned_fields():
    from contracts.schemas import Route, TraceResult

    assert list(Route.model_fields) == [
        "rail", "corridor", "amount", "currency_from", "currency_to", "fee", "spread_cost", "tax_lines",
        "arrival_hours", "status", "simulated", "limit_ok", "blocked_reason", "rule_id", "fee_source_url",
        "rate_source", "quoted_at", "purpose", "payee_id",
    ]
    for name in ("purpose", "payee_id"):
        assert Route.model_fields[name].default is None
    assert TraceResult.model_fields["typical_duration_hours"].default is None
    assert not TraceResult.model_fields["typical_duration_hours"].is_required()


def test_action_carries_an_optional_plan_update_and_the_plan_names_the_fields_it_may_change():
    from contracts.schemas import PLAN_UPDATE_FIELDS, Action

    assert Action.model_fields["plan_update"].default is None
    assert PLAN_UPDATE_FIELDS == ("backup_instrument", "backup_route", "wallet_token_present", "cash_plan")
