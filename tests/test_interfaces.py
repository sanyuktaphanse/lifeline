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

FROZEN_INTERFACES = {
    MandateEngine: {"check", "confirmation_token_for"},
    Ledger: {"append", "verify", "entries", "head"},
    Anchor: {"anchor", "verify"},
    Router: {"quote", "precheck"},
    Rail: {"name", "simulated", "execute", "status", "freeze"},
    Council: {"deliberate"},
    ModelAdapter: {"complete"},
    Translator: {"explain"},
}


def _mandate() -> Mandate:
    now = datetime.now(timezone.utc)
    return Mandate(
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
