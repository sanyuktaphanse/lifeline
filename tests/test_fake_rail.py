import inspect
from datetime import datetime, timedelta, timezone
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


def _route(amount: str = "1200", rail: str = "wise") -> Route:
    return Route(
        rail=rail,
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


def test_name_and_simulated_are_chosen_when_the_rail_is_made():
    rail = FakeRail(name="wise", simulated=False)

    receipt = _execute(rail, "txn-0700-rent")

    assert rail.name == "wise"
    assert rail.simulated is False
    assert receipt.simulated is False


def test_the_receipt_names_the_rail_that_executed_it_not_the_route():
    receipt = _execute(FakeRail(name="wise_backend"), "txn-0700-rent")

    assert receipt.rail == "wise_backend"


def test_the_receipt_takes_simulated_from_the_rail_not_the_route():
    route = _route().model_copy(update={"simulated": False})

    receipt = FakeRail().execute(route, MANDATE_REF, "txn-0700-rent", TOKEN)

    assert receipt.simulated is True


def test_execute_returns_a_completed_receipt_carrying_both_references():
    receipt = _execute(FakeRail(), "txn-0700-rent")

    assert isinstance(receipt, Receipt)
    assert receipt.status is ReceiptStatus.COMPLETED
    assert receipt.rail == "fake"
    assert receipt.amount == Decimal("1200")
    assert receipt.currency == "SGD"
    assert receipt.mandate_ref == MANDATE_REF
    assert receipt.idempotency_key == "txn-0700-rent"
    assert receipt.simulated is True
    assert receipt.executed_at.tzinfo is not None


def test_reusing_a_key_with_the_same_details_returns_the_original_receipt():
    rail = FakeRail()

    first = _execute(rail, "txn-0700-rent")
    again = _execute(rail, "txn-0700-rent")

    assert again == first


def test_a_fresh_quote_of_the_same_route_counts_as_the_same_details():
    rail = FakeRail()

    first = rail.execute(_route(), MANDATE_REF, "txn-0700-rent", TOKEN)
    requoted = _route().model_copy(
        update={"quoted_at": first.executed_at + timedelta(minutes=5)}
    )

    assert rail.execute(requoted, MANDATE_REF, "txn-0700-rent", TOKEN) == first


@pytest.mark.parametrize(
    ("route_changes", "mandate_ref"),
    [
        ({"amount": Decimal("999")}, MANDATE_REF),
        ({"rail": "bank_wire"}, MANDATE_REF),
        ({"fee": Decimal("25")}, MANDATE_REF),
        ({}, "mandate-rent-other"),
    ],
    ids=["amount", "rail", "fee", "mandate_ref"],
)
def test_reusing_a_key_with_any_difference_raises(route_changes, mandate_ref):
    rail = FakeRail()
    original = rail.execute(_route(), MANDATE_REF, "txn-0700-rent", TOKEN)
    changed = _route().model_copy(update=route_changes)

    with pytest.raises(RailError, match="txn-0700-rent"):
        rail.execute(changed, mandate_ref, "txn-0700-rent", TOKEN)

    assert rail.execute(_route(), MANDATE_REF, "txn-0700-rent", TOKEN) == original


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


def test_a_failed_key_is_not_recorded_so_another_route_may_retry_it():
    rail = FakeRail()

    with pytest.raises(RailError):
        rail.execute(_route(), MANDATE_REF, FAIL_ONCE_KEY, TOKEN)
    retry = rail.execute(_route(rail="bank_wire"), MANDATE_REF, FAIL_ONCE_KEY, TOKEN)

    assert retry.status is ReceiptStatus.COMPLETED


def test_fail_once_keys_can_be_chosen_when_the_rail_is_made():
    rail = FakeRail(fail_once_keys={"student_001:t1:propose_transfer:1"})

    with pytest.raises(RailError):
        _execute(rail, "student_001:t1:propose_transfer:1")

    assert _execute(rail, FAIL_ONCE_KEY).status is ReceiptStatus.COMPLETED


def test_failure_leaves_no_receipt_behind():
    rail = FakeRail()

    with pytest.raises(RailError):
        _execute(rail, FAIL_ONCE_KEY)
    other = _execute(rail, "txn-0700-rent")
    retry = _execute(rail, FAIL_ONCE_KEY)

    assert other.receipt_id != retry.receipt_id


def test_status_returns_the_scripted_trace_stamped_with_the_receipts_stage_time():
    scripted = _trace("fake-0001").model_copy(update={"stage_entered_at": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    rail = FakeRail(traces={"fake-0001": scripted})

    receipt = _execute(rail, "txn-0700-rent")

    assert receipt.receipt_id == "fake-0001"
    assert rail.status(receipt.receipt_id) == scripted.model_copy(update={"stage_entered_at": receipt.stage_entered_at})


def test_a_scripted_trace_for_a_receipt_not_yet_issued_keeps_its_scripted_time():
    scripted = _trace("fake-0009")

    assert FakeRail(traces={"fake-0009": scripted}).status("fake-0009") == scripted


def test_a_restored_receipt_numbers_the_next_one_and_counts_as_already_paid():
    first = FakeRail()
    original = _execute(first, "txn-0700-rent")

    rail = FakeRail(traces={"fake-0001": _trace("fake-0001")})
    rail.restore(original, _route(), MANDATE_REF)

    assert _execute(rail, "txn-0700-rent") == original
    assert _execute(rail, "txn-0800-rent").receipt_id == "fake-0002"
    assert rail.status("fake-0001").stage_entered_at == original.stage_entered_at
    with pytest.raises(RailError):
        _execute(rail, "txn-0700-rent", amount="999")


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


def test_receipt_ids_carry_the_rail_name_so_two_rails_never_share_one():
    wise = _execute(FakeRail(name="wise"), "txn-0700-rent")
    wire = FakeRail(name="bank_wire").execute(_route(rail="bank_wire"), MANDATE_REF, "txn-0800-rent", TOKEN)

    assert (wise.receipt_id, wire.receipt_id) == ("wise-0001", "bank_wire-0001")
    assert _execute(FakeRail(), "txn-0900-rent").receipt_id == "fake-0001"
