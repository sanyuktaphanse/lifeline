from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.schemas import ReceiptStatus
from rails.fake_rail import FakeRail
from rails.inbound import inbound_from_fixture, seed_inbound

BLOCK = {
    "wise": [
        {
            "receipt_id": "wise-in-0001",
            "amount": "500",
            "currency": "SGD",
            "corridor": "SG>SG",
            "status": "in_transit",
            "sender": "parent",
            "sent_hours_ago": 30,
        }
    ]
}


def _rails():
    return {"wise": FakeRail(name="wise", simulated=False), "sim": FakeRail(name="sim", simulated=True)}


def test_a_fixture_block_becomes_receipts_per_rail_marked_as_inbound():
    rails = _rails()
    before = datetime.now(timezone.utc)

    receipts = inbound_from_fixture(BLOCK, rails)

    receipt = receipts["wise"][0].receipt
    assert receipts["wise"][0].route.corridor == "SG>SG"
    assert receipt.receipt_id == "wise-in-0001"
    assert (receipt.amount, receipt.currency, receipt.status) == (Decimal("500"), "SGD", ReceiptStatus.IN_TRANSIT)
    assert receipt.mandate_ref == "inbound:parent"
    assert receipt.idempotency_key == "inbound:wise-in-0001"
    assert receipt.rail == "wise"
    assert receipt.simulated is False
    sent = before - timedelta(hours=30)
    assert abs((receipt.executed_at - sent).total_seconds()) < 5
    assert receipt.stage_entered_at == receipt.executed_at


def test_a_receipt_on_a_simulated_rail_is_simulated():
    receipts = inbound_from_fixture({"sim": [{**BLOCK["wise"][0], "receipt_id": "sim-in-0001"}]}, _rails())

    assert receipts["sim"][0].receipt.simulated is True
    assert receipts["sim"][0].route.simulated is True


def test_seeding_gives_each_rail_its_receipts_and_returns_where_each_lives():
    rails = _rails()

    where = seed_inbound(rails, inbound_from_fixture(BLOCK, rails))

    assert where == {"wise-in-0001": "wise"}
    assert rails["wise"]._receipts["inbound:wise-in-0001"].receipt_id == "wise-in-0001"


def test_a_block_naming_a_rail_that_is_not_built_is_refused():
    with pytest.raises(ValueError, match="revolut"):
        inbound_from_fixture({"revolut": BLOCK["wise"]}, _rails())


def test_an_empty_block_seeds_nothing():
    rails = _rails()

    assert seed_inbound(rails, inbound_from_fixture(None, rails)) == {}
