from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import ReceiptStatus
from rails.fake_router import FakeRouter
from rails.knowledge.loader import load_knowledge
from rails.sim.base import SCRIPTS
from rails.sim.upi_paynow import UpiPayNowSimRail

CAP = Decimal(str(load_knowledge()["in_upi_paynow_cap_002"]["values"]["daily_cap"]))


def _route(amount="25000", purpose="gift", currency="INR"):
    route = FakeRouter().quote("IN>SG", Decimal(amount), purpose, "normal")[0]
    return route.model_copy(update={"currency_from": currency, "payee_id": "student_001_sg"})


def _pay(rail, amount="25000", purpose="gift", key="upi-key-0001", mandate_ref="mandate-parent-v1", currency="INR"):
    return rail.execute(_route(amount, purpose, currency), mandate_ref, key, "token")


def test_the_rail_is_a_simulated_rail_named_upi_paynow_sim():
    rail = UpiPayNowSimRail()

    assert isinstance(rail, Rail)
    assert (rail.name, rail.simulated) == ("upi_paynow_sim", True)


@pytest.mark.parametrize("purpose", ["maintenance_of_relatives_abroad", "gift"])
def test_a_permitted_purpose_within_the_cap_is_paid_as_a_simulation(purpose):
    receipt = _pay(UpiPayNowSimRail(), purpose=purpose)

    assert receipt.simulated is True
    assert receipt.rail == "upi_paynow_sim"
    assert receipt.receipt_id == "upi_paynow_sim-0001"
    assert receipt.status is ReceiptStatus.CREATED
    assert receipt.amount == Decimal("25000")


@pytest.mark.parametrize("purpose", ["business", "rent", None])
def test_any_other_purpose_is_refused_naming_the_entry(purpose):
    with pytest.raises(RailError, match="in_upi_paynow_purpose_001"):
        _pay(UpiPayNowSimRail(), purpose=purpose)


def test_one_transfer_above_the_cap_is_refused_naming_the_cap_entry():
    with pytest.raises(RailError, match="in_upi_paynow_cap_002"):
        _pay(UpiPayNowSimRail(), amount=str(CAP + Decimal("0.01")))


def test_the_cap_counts_the_whole_day_for_one_sender():
    rail = UpiPayNowSimRail()
    _pay(rail, amount=str(CAP - Decimal("100")), key="upi-key-0001")

    with pytest.raises(RailError, match="in_upi_paynow_cap_002"):
        _pay(rail, amount="100.01", key="upi-key-0002")
    _pay(rail, amount="100", key="upi-key-0003")
    _pay(rail, amount="100", key="upi-key-0004", mandate_ref="mandate-other-parent-v1")


def test_an_amount_in_a_currency_the_entry_does_not_give_is_refused():
    with pytest.raises(RailError, match="no sourced UPI to PayNow limit in SGD"):
        _pay(UpiPayNowSimRail(), currency="SGD")


def test_a_refused_payment_records_no_key_so_a_corrected_retry_is_not_a_reuse():
    rail = UpiPayNowSimRail()
    with pytest.raises(RailError):
        _pay(rail, purpose="business")

    assert _pay(rail, purpose="gift").receipt_id == "upi_paynow_sim-0001"


def test_a_key_reused_for_the_same_request_returns_the_same_receipt_and_for_another_raises():
    rail = UpiPayNowSimRail()
    first = _pay(rail)

    assert _pay(rail) == first
    with pytest.raises(RailError, match="already used"):
        _pay(rail, amount="100")


def test_the_trace_names_the_entry_and_has_no_sourced_duration():
    rail = UpiPayNowSimRail()
    receipt = _pay(rail)

    trace = rail.status(receipt.receipt_id)

    assert trace.typical_duration_hours is None
    assert trace.typical_duration_source.startswith("in_upi_paynow_cap_002")
    assert any("no sourced duration" in step and "in_upi_paynow_cap_002" in step for step in trace.next_steps)
    assert any("simulated" in step for step in trace.next_steps)


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_is_accepted(script):
    rail = UpiPayNowSimRail(script=script)

    assert rail.status(_pay(rail).receipt_id).receipt_id == "upi_paynow_sim-0001"


def test_an_unknown_script_is_refused():
    with pytest.raises(ValueError, match="normal"):
        UpiPayNowSimRail(script="instant_riches")


def test_normal_completes_by_the_simulated_clock():
    rail = UpiPayNowSimRail()
    receipt = _pay(rail)

    assert rail.status(receipt.receipt_id).status is ReceiptStatus.CREATED
    later = datetime.now(timezone.utc) + timedelta(days=1)
    assert rail.status(receipt.receipt_id, now=later).status is ReceiptStatus.COMPLETED


@pytest.mark.parametrize(
    ("script", "status"),
    [("held_for_review", ReceiptStatus.HELD_FOR_REVIEW), ("returned", ReceiptStatus.RETURNED)],
)
def test_review_and_return_scripts_show_their_status_at_once_and_after(script, status):
    rail = UpiPayNowSimRail(script=script)
    receipt = _pay(rail)

    assert receipt.status is status
    later = datetime.now(timezone.utc) + timedelta(days=30)
    assert rail.status(receipt.receipt_id, now=later).status is status


def test_delayed_never_completes_and_says_so():
    rail = UpiPayNowSimRail(script="delayed")
    receipt = _pay(rail)

    trace = rail.status(receipt.receipt_id, now=datetime.now(timezone.utc) + timedelta(days=30))

    assert trace.status is not ReceiptStatus.COMPLETED
    assert any("delayed" in warning for warning in trace.warnings)


def test_scam_text_puts_a_release_fee_demand_in_the_trace():
    rail = UpiPayNowSimRail(script="scam_text")

    trace = rail.status(_pay(rail).receipt_id)

    assert any("release fee" in step for step in trace.next_steps)


def test_an_unknown_receipt_raises():
    with pytest.raises(RailError):
        UpiPayNowSimRail().status("upi_paynow_sim-9999")


def test_the_rail_freezes_no_card():
    assert UpiPayNowSimRail().freeze("wise:card_01").status.value == "failed"


# What the second number audit found, each now a test.

import rails.sim.upi_paynow as upi_module
from contracts.schemas import Receipt


def _freeze_clock(monkeypatch, frozen):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.astimezone(tz) if tz else frozen

    monkeypatch.setattr(upi_module, "datetime", Frozen)


def _restore(rail, amount, executed_at, mandate_ref):
    receipt = Receipt(
        receipt_id="upi_paynow_sim-0001",
        rail="upi_paynow_sim",
        amount=Decimal(amount),
        currency="INR",
        status=ReceiptStatus.COMPLETED,
        stage_entered_at=executed_at,
        mandate_ref=mandate_ref,
        idempotency_key="restored-key-0001",
        simulated=True,
        executed_at=executed_at,
    )
    rail.restore(receipt, _route(str(amount)), mandate_ref)


def test_the_cap_counts_the_sender_across_mandate_versions():
    rail = UpiPayNowSimRail()
    _pay(rail, amount=str(CAP), mandate_ref="mandate-parent-v1", key="upi-key-0001")

    with pytest.raises(RailError, match="in_upi_paynow_cap_002"):
        _pay(rail, amount=str(CAP), mandate_ref="mandate-parent-v2", key="upi-key-0002")


def test_the_cap_day_is_the_senders_day_in_india(monkeypatch):
    rail = UpiPayNowSimRail()
    first = datetime(2026, 10, 8, 23, 0, tzinfo=timezone.utc)
    second = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)
    _restore(rail, CAP, first, "mandate-parent-v1")
    _freeze_clock(monkeypatch, second)

    with pytest.raises(RailError, match="in_upi_paynow_cap_002"):
        _pay(rail, amount=str(CAP), key="upi-key-0002")


def test_a_payment_the_next_day_in_india_has_its_own_cap(monkeypatch):
    rail = UpiPayNowSimRail()
    _restore(rail, CAP, datetime(2026, 10, 8, 17, 0, tzinfo=timezone.utc), "mandate-parent-v1")
    _freeze_clock(monkeypatch, datetime(2026, 10, 8, 19, 0, tzinfo=timezone.utc))

    assert _pay(rail, amount=str(CAP), key="upi-key-0002").receipt_id == "upi_paynow_sim-0002"


def test_the_cap_sum_is_exact_whatever_the_decimal_precision():
    rail = UpiPayNowSimRail()
    _pay(rail, amount=str(CAP), key="upi-key-0001")

    with pytest.raises(RailError, match="in_upi_paynow_cap_002"):
        _pay(rail, amount="1E-24", key="upi-key-0002")
