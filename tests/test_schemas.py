from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.schemas import ActionType, Mandate, Receipt, Route, Tier
from core.tiers import TIERS

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _route_fields(**overrides) -> dict:
    fields = {
        "rail": "wise",
        "corridor": "SG>BR",
        "amount": Decimal("1200"),
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": Decimal("8.40"),
        "spread_cost": Decimal("3.10"),
        "tax_lines": [{"name": "IOF", "amount": "4.20"}],
        "arrival_hours": 24,
        "status": "up",
        "simulated": False,
        "limit_ok": True,
        "quoted_at": NOW,
    }
    fields.update(overrides)
    return fields


def _receipt_fields(**overrides) -> dict:
    fields = {
        "receipt_id": "rcpt-0001",
        "rail": "wise",
        "amount": Decimal("1200"),
        "currency": "SGD",
        "status": "in_transit",
        "stage_entered_at": NOW,
        "mandate_ref": "mandate-student_001",
        "simulated": False,
        "executed_at": NOW,
    }
    fields.update(overrides)
    return fields


def _assert_rejected_on_status(model, fields: dict) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model(**fields)
    assert [error["loc"] for error in excinfo.value.errors()] == [("status",)]


def test_route_accepts_every_known_status():
    for status in ("up", "degraded", "down", "simulated"):
        assert Route(**_route_fields(status=status)).status.value == status


def test_route_rejects_an_unknown_status():
    _assert_rejected_on_status(Route, _route_fields(status="maintenance"))


def test_receipt_accepts_every_known_status():
    statuses = (
        "created",
        "funded",
        "in_transit",
        "held_for_review",
        "completed",
        "failed",
        "returned",
    )
    for status in statuses:
        assert Receipt(**_receipt_fields(status=status)).status.value == status


def test_receipt_rejects_an_unknown_status():
    _assert_rejected_on_status(Receipt, _receipt_fields(status="lost"))


def test_trace_transfer_and_precheck_are_tier_zero():
    assert TIERS[ActionType.TRACE_TRANSFER] is Tier.T0
    assert TIERS[ActionType.PRECHECK] is Tier.T0


def test_standing_mandates_default_to_empty():
    mandate = Mandate(
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
        valid_from=NOW - timedelta(days=30),
        valid_until=NOW + timedelta(days=30),
    )

    assert mandate.standing_mandates == []
