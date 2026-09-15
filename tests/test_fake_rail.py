import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from contracts.interfaces import Rail
from contracts.schemas import Receipt, ReceiptStatus, Route, RouteStatus, TraceResult
from rails.fake_rail import FAIL_ONCE_KEY, FakeRail, RailError

TOKEN = "confirm-token-test"


def _route(rail: str = "wise", amount: str = "1200") -> Route:
    return Route(
        rail=rail,
        corridor="SG>BR",
        amount=Decimal(amount),
        currency_from="SGD",
        currency_to="BRL",
        fee=Decimal("5.60"),
        spread_cost=Decimal("4.80"),
        tax_lines=[],
        arrival_hours=24,
        status=RouteStatus.UP,
        simulated=False,
        limit_ok=True,
        quoted_at=datetime.now(timezone.utc),
    )


def _trace(receipt_id: str) -> TraceResult:
    return TraceResult(
        receipt_id=receipt_id,
        status=ReceiptStatus.IN_TRANSIT,
        stage_entered_at=datetime.now(timezone.utc),
        typical_duration_hours=24,
        typical_duration_source="fixture",
        next_steps=["Wait for the recipient bank to credit the payment."],
        warnings=[],
    )


def test_fake_rail_implements_the_rail():
    rail = FakeRail()

    assert isinstance(rail, Rail)
    assert not inspect.isabstract(FakeRail)
    assert rail.name == "fake"
    assert rail.simulated is True


def test_execute_returns_a_completed_receipt_for_the_route():
    receipt = FakeRail().execute(_route(), "txn-0700-rent", TOKEN)

    assert isinstance(receipt, Receipt)
    assert receipt.status is ReceiptStatus.COMPLETED
    assert receipt.rail == "wise"
    assert receipt.amount == Decimal("1200")
    assert receipt.currency == "SGD"
    assert receipt.mandate_ref == "txn-0700-rent"
    assert receipt.simulated is True
    assert receipt.executed_at.tzinfo is not None


def test_execute_is_idempotent_on_mandate_ref():
    rail = FakeRail()

    first = rail.execute(_route(), "txn-0700-rent", TOKEN)
    again = rail.execute(_route(amount="999"), "txn-0700-rent", TOKEN)

    assert again == first


def test_different_mandate_refs_get_different_receipts():
    rail = FakeRail()

    first = rail.execute(_route(), "txn-0700-rent", TOKEN)
    second = rail.execute(_route(), "txn-0800-rent", TOKEN)

    assert first.receipt_id != second.receipt_id


def test_returned_receipts_do_not_share_state():
    rail = FakeRail()

    first = rail.execute(_route(), "txn-0700-rent", TOKEN)
    first.status = ReceiptStatus.FAILED

    assert rail.execute(_route(), "txn-0700-rent", TOKEN).status is ReceiptStatus.COMPLETED


def test_fail_once_key_fails_the_first_time_then_succeeds_once():
    rail = FakeRail()

    with pytest.raises(RailError):
        rail.execute(_route(), FAIL_ONCE_KEY, TOKEN)
    retry = rail.execute(_route(), FAIL_ONCE_KEY, TOKEN)
    again = rail.execute(_route(), FAIL_ONCE_KEY, TOKEN)

    assert FAIL_ONCE_KEY == "txn-fail-once"
    assert retry.status is ReceiptStatus.COMPLETED
    assert again == retry


def test_failure_leaves_no_receipt_behind():
    rail = FakeRail()

    with pytest.raises(RailError):
        rail.execute(_route(), FAIL_ONCE_KEY, TOKEN)
    other = rail.execute(_route(), "txn-0700-rent", TOKEN)
    retry = rail.execute(_route(), FAIL_ONCE_KEY, TOKEN)

    assert other.receipt_id != retry.receipt_id


def test_status_returns_the_scripted_trace():
    scripted = _trace("fake-0001")
    rail = FakeRail(traces={"fake-0001": scripted})

    receipt = rail.execute(_route(), "txn-0700-rent", TOKEN)

    assert receipt.receipt_id == "fake-0001"
    assert rail.status(receipt.receipt_id) == scripted


def test_status_results_do_not_share_state():
    rail = FakeRail(traces={"fake-0001": _trace("fake-0001")})

    rail.status("fake-0001").warnings.append("tampered")

    assert rail.status("fake-0001").warnings == []


def test_status_for_an_unscripted_receipt_raises():
    with pytest.raises(RailError, match="fake-0404"):
        FakeRail().status("fake-0404")


def test_freeze_is_supported_for_wise():
    assert FakeRail().freeze("wise:card_01") is True


def test_freeze_is_not_supported_for_revolut():
    assert FakeRail().freeze("revolut:card_01") is False


@pytest.mark.parametrize("instrument_id", ["monzo:card_01", "card_01", ""])
def test_freeze_raises_for_an_unknown_issuer(instrument_id):
    with pytest.raises(RailError):
        FakeRail().freeze(instrument_id)
