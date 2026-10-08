from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import ReceiptStatus
from rails.fake_router import FakeRouter
from rails.sim.base import SCRIPTS
from rails.sim.pix import PixSimRail
from tests.test_agent import RENT, RENT_REQUEST, USER, _call, _setup, _user


def _route(payee="landlord_sp"):
    route = next(r for r in FakeRouter().quote("SG>BR", Decimal("1200"), "rent", "normal") if r.rail == "sim_pix")
    return route.model_copy(update={"payee_id": payee})


def _rail(script="normal"):
    return PixSimRail(pix_key_on_file=["landlord_sp"], script=script)


def test_the_rail_keeps_the_name_and_corridor_scenarios_rely_on():
    rail = _rail()

    assert isinstance(rail, Rail)
    assert (rail.name, rail.simulated) == ("sim_pix", True)
    assert _route().corridor == "SG>BR"
    assert _route().rule_id == "br_pix_instant_001"


def test_a_payee_with_a_pix_key_on_file_is_paid_at_once_because_pix_settles_in_real_time():
    receipt = _rail().execute(_route(), "mandate-student_001-v1", "pix-key-0001", "token")

    assert receipt.receipt_id == "sim_pix-0001"
    assert receipt.status is ReceiptStatus.COMPLETED
    assert receipt.simulated is True


@pytest.mark.parametrize("payee", ["landlord_two", None])
def test_a_payee_with_no_pix_key_on_file_is_refused_naming_the_entry(payee):
    with pytest.raises(RailError, match="br_pix_keys_002"):
        _rail().execute(_route(payee), "mandate-student_001-v1", "pix-key-0001", "token")


def test_the_rail_holds_payee_ids_and_never_a_key():
    rail = _rail()

    assert rail.pix_key_on_file == frozenset({"landlord_sp"})


def test_the_trace_gives_the_real_time_duration_from_its_entry():
    rail = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "pix-key-0001", "token")

    trace = rail.status(receipt.receipt_id)

    assert trace.status is ReceiptStatus.COMPLETED
    assert (trace.typical_duration_hours, trace.typical_duration_source) == (0, "br_pix_instant_001")
    assert "sim_pix stage: completed." in trace.next_steps
    assert not any("no sourced duration" in step for step in trace.next_steps)


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_is_accepted(script):
    rail = _rail(script)

    assert rail.status(rail.execute(_route(), "m-ref-0001", "pix-key-0001", "t").receipt_id).receipt_id == "sim_pix-0001"


def test_delayed_stops_at_created_and_says_so():
    rail = _rail("delayed")
    receipt = rail.execute(_route(), "m-ref-0001", "pix-key-0001", "t")

    trace = rail.status(receipt.receipt_id, now=datetime.now(timezone.utc) + timedelta(days=3))

    assert receipt.status is ReceiptStatus.CREATED
    assert trace.status is ReceiptStatus.CREATED
    assert trace.warnings


def test_a_loop_paying_a_payee_without_a_pix_key_gets_no_receipt_and_a_note():
    rails = {"sim_pix": _rail()}
    s = _setup([_call("propose_transfer", {**RENT, "payee_id": "landlord_two"})], rails=rails)
    s.mandates[USER] = s.mandates[USER].model_copy(update={"allowed_payees": {"landlord_sp", "landlord_two"}})
    proposed = s.loop.handle(USER, _user("Send 1,200 SGD rent to landlord_two in Brazil"))

    reply = s.loop.handle(USER, _user(""), confirmation_token=proposed.confirmation.confirmation_token)

    assert reply.receipt is None
    note = [e.payload for e in s.ledger.entries() if e.kind == "note" and "rail_error" in e.payload][0]
    assert "br_pix_keys_002" in note["rail_error"]
    assert note["executed"] is False


def test_a_loop_paying_the_landlord_over_pix_gets_the_simulated_receipt():
    s = _setup([_call("propose_transfer", RENT)], rails={"sim_pix": _rail()})
    proposed = s.loop.handle(USER, _user(RENT_REQUEST))

    reply = s.loop.handle(USER, _user(""), confirmation_token=proposed.confirmation.confirmation_token)

    assert reply.receipt.receipt_id == "sim_pix-0001"
    assert "This was a simulation. No real money moved." in reply.text
