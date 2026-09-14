from decimal import Decimal

from contracts.schemas import Action, ActionType, Mandate
from core.mandate import check


def _mandate() -> Mandate:
    return Mandate(
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
    )


def test_transfer_over_per_txn_limit_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0001-test",
        amount=Decimal("1600"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R08" in decision.rule_ids


def test_transfer_to_unknown_payee_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0002-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="stranger_42",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R06" in decision.rule_ids


def test_transfer_on_disallowed_corridor_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0003-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>IN",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R05" in decision.rule_ids
