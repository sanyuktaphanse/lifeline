import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import (
    FreezeResult,
    FreezeStatus,
    Receipt,
    ReceiptStatus,
    Route,
    RouteStatus,
    TraceResult,
)
from rails.fake_rail import FAIL_ONCE_KEY, REVOLUT_FREEZE_DEEP_LINK, FakeRail

TOKEN = "confirm-token-test"
MANDATE_REF = "mandate-rent-landlord_sp"


def _route(amount: str = "1200") -> Route:
    return Route(
        rail="wise",
        corridor="SG>BR",
        amount=Decimal(amount),
        currency_from="SGD",
        currency_to="BRL",
        fee=Decimal("5.60"),
        spread_cost=Decimal("0"),
        tax_lines=[],
        arrival_hours=24,
        status=RouteStatus.UP,
        simulated=False,
        limit_ok=True,
        quoted_at=datetime.now(timezone.utc),
    )


def _execute(rail: FakeRail, key: str, amount: str = "1200", mandate_ref: str = MANDATE_REF):
    return rail.execute(_route(amount), mandate_ref, key, TOKEN)


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


def test_execute_returns_a_completed_receipt_carrying_both_references():
    receipt = _execute(FakeRail(), "txn-0700-rent")

    assert isinstance(receipt, Receipt)
    assert receipt.status is ReceiptStatus.COMPLETED
    assert receipt.rail == "wise"
    assert receipt.amount == Decimal("1200")
    assert receipt.currency == "SGD"
    assert receipt.mandate_ref == MANDATE_REF
    assert receipt.idempotency_key == "txn-0700-rent"
    assert receipt.simulated is True
    assert receipt.executed_at.tzinfo is not None


def test_execute_is_idempotent_on_the_idempotency_key():
    rail = FakeRail()

    first = _execute(rail, "txn-0700-rent")
    again = _execute(rail, "txn-0700-rent", amount="999")

    assert again == first


def test_one_mandate_can_pay_again_under_a_new_idempotency_key():
    rail = FakeRail()

    september = _execute(rail, "txn-0700-rent")
    october = _execute(rail, "txn-0800-rent")

    assert september.receipt_id != october.receipt_id
    assert september.mandate_ref == october.mandate_ref


def test_returned_receipts_do_not_share_state():
    rail = FakeRail()

    first = _execute(rail, "txn-0700-rent")
    first.status = ReceiptStatus.FAILED

    assert _execute(rail, "txn-0700-rent").status is ReceiptStatus.COMPLETED


def test_fail_once_key_fails_the_first_time_then_succeeds_once():
    rail = FakeRail()

    with pytest.raises(RailError):
        _execute(rail, FAIL_ONCE_KEY)
    retry = _execute(rail, FAIL_ONCE_KEY)
    again = _execute(rail, FAIL_ONCE_KEY)

    assert FAIL_ONCE_KEY == "txn-fail-once"
    assert retry.status is ReceiptStatus.COMPLETED
    assert again == retry


def test_fail_once_is_matched_on_the_idempotency_key_not_the_mandate_ref():
    receipt = _execute(FakeRail(), "txn-0700-rent", mandate_ref=FAIL_ONCE_KEY)

    assert receipt.status is ReceiptStatus.COMPLETED


def test_failure_leaves_no_receipt_behind():
    rail = FakeRail()

    with pytest.raises(RailError):
        _execute(rail, FAIL_ONCE_KEY)
    other = _execute(rail, "txn-0700-rent")
    retry = _execute(rail, FAIL_ONCE_KEY)

    assert other.receipt_id != retry.receipt_id


def test_status_returns_the_scripted_trace():
    scripted = _trace("fake-0001")
    rail = FakeRail(traces={"fake-0001": scripted})

    receipt = _execute(rail, "txn-0700-rent")

    assert receipt.receipt_id == "fake-0001"
    assert rail.status(receipt.receipt_id) == scripted


def test_status_results_do_not_share_state():
    rail = FakeRail(traces={"fake-0001": _trace("fake-0001")})

    rail.status("fake-0001").warnings.append("tampered")

    assert rail.status("fake-0001").warnings == []


def test_status_for_an_unscripted_receipt_raises():
    with pytest.raises(RailError, match="fake-0404"):
        FakeRail().status("fake-0404")


def test_freeze_is_done_for_wise():
    assert FakeRail().freeze("wise:card_01") == FreezeResult(status=FreezeStatus.DONE)


def test_freeze_is_not_supported_for_revolut_and_offers_a_deep_link():
    result = FakeRail().freeze("revolut:card_01")

    assert result.status is FreezeStatus.NOT_SUPPORTED
    assert result.deep_link == REVOLUT_FREEZE_DEEP_LINK
    assert result.reason


@pytest.mark.parametrize("instrument_id", ["monzo:card_01", "card_01", ""])
def test_freeze_fails_with_a_reason_for_an_unknown_issuer(instrument_id):
    result = FakeRail().freeze(instrument_id)

    assert result.status is FreezeStatus.FAILED
    assert result.deep_link is None
    assert result.reason
