from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

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


def test_transfer_with_disallowed_purpose_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0004-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="crypto",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R07" in decision.rule_ids


def test_transfer_breaking_two_rules_reports_both():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0007-test",
        amount=Decimal("1600"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="stranger_42",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R06" in decision.rule_ids
    assert "R08" in decision.rule_ids
    assert len(decision.reasons) == 2


def test_transfer_in_wrong_currency_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0005-test",
        amount=Decimal("1200"),
        currency="USD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R04" in decision.rule_ids


def test_transfer_within_mandate_is_allowed():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0006-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is True
    assert decision.rule_ids == []


def test_replayed_idempotency_key_is_refused_on_its_own():
    history = [_executed_today("txn-0200-done", "1400")]
    action = _executed_today("txn-0200-done", "1400")

    decision = check(action, _mandate(), history)

    assert decision.allowed is False
    assert decision.rule_ids == ["R10"]


def test_requested_at_defaults_to_an_aware_utc_timestamp():
    before = datetime.now(timezone.utc)
    action = Action(type=ActionType.READ_BALANCE, idempotency_key="txn-0008-test")
    after = datetime.now(timezone.utc)

    assert action.requested_at.utcoffset() == timedelta(0)
    assert before <= action.requested_at <= after

    with pytest.raises(ValidationError):
        Action(
            type=ActionType.READ_BALANCE,
            idempotency_key="txn-0009-test",
            requested_at=datetime(2026, 9, 14, 12, 0, 0),
        )


def test_check_accepts_prior_history_without_changing_the_verdict():
    mandate = _mandate()
    earlier = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0010-test",
        amount=Decimal("400"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0011-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    assert check(action, mandate, [earlier]) == check(action, mandate)


def _executed_today(key: str, amount: str) -> Action:
    return Action(
        type=ActionType.TRANSFER,
        idempotency_key=key,
        amount=Decimal(amount),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )


def test_transfer_over_daily_limit_with_history_is_denied():
    history = [_executed_today("txn-0100-earlier", "1400")]
    action = _executed_today("txn-0101-test", "1200")

    decision = check(action, _mandate(), history)

    assert decision.allowed is False
    assert "R09" in decision.rule_ids
    assert any("2600" in reason for reason in decision.reasons)


def test_transfer_within_daily_limit_with_history_is_allowed():
    history = [_executed_today("txn-0100-earlier", "1400")]
    action = _executed_today("txn-0102-test", "1000")

    decision = check(action, _mandate(), history)

    assert decision.allowed is True
    assert decision.rule_ids == []
