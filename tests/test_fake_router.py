import inspect
from decimal import Decimal

import pytest

from contracts.interfaces import Router
from contracts.schemas import PrecheckResult, RouteStatus
from rails.fake_router import FakeRouter


def _quote(corridor: str, amount: str = "1200", purpose: str = "rent"):
    return FakeRouter().quote(corridor, Decimal(amount), purpose, "normal")


def _by_rail(routes):
    return {route.rail: route for route in routes}


def test_fake_router_implements_the_router():
    router = FakeRouter()

    assert isinstance(router, Router)
    assert not inspect.isabstract(FakeRouter)


def test_sg_to_br_returns_wise_sim_pix_and_bank_wire():
    routes = _quote("SG>BR")

    assert [route.rail for route in routes] == ["wise", "sim_pix", "bank_wire"]
    for route in routes:
        assert route.corridor == "SG>BR"
        assert route.amount == Decimal("1200")
        assert route.currency_from == "SGD"
        assert route.currency_to == "BRL"
        assert route.status is RouteStatus.UP
        assert route.limit_ok is True
        assert route.blocked_reason is None
        assert route.rule_id is None
        assert route.quoted_at.tzinfo is not None


def test_wise_route_has_its_fee_and_no_spread():
    wise = _by_rail(_quote("SG>BR"))["wise"]

    assert wise.fee == Decimal("5.60")
    assert wise.spread_cost == Decimal("0")
    assert wise.arrival_hours == 24
    assert wise.simulated is False


def test_sim_pix_route_is_simulated_and_arrives_in_an_hour():
    sim_pix = _by_rail(_quote("SG>BR"))["sim_pix"]

    assert sim_pix.simulated is True
    assert sim_pix.arrival_hours == 1


def test_bank_wire_route_has_its_fee_spread_and_arrival():
    bank_wire = _by_rail(_quote("SG>BR"))["bank_wire"]

    assert bank_wire.fee == Decimal("25")
    assert bank_wire.spread_cost == Decimal("30.00")
    assert bank_wire.arrival_hours == 72
    assert bank_wire.simulated is False


def test_bank_wire_spread_is_two_and_a_half_percent_of_the_amount():
    bank_wire = _by_rail(_quote("SG>BR", amount="500"))["bank_wire"]

    assert bank_wire.spread_cost == Decimal("12.50")


@pytest.mark.parametrize("purpose", ["allowance", "family_support"])
def test_in_to_sg_returns_one_open_upi_paynow_route(purpose):
    routes = _quote("IN>SG", amount="25000", purpose=purpose)

    assert len(routes) == 1
    route = routes[0]
    assert route.rail == "upi_paynow"
    assert route.corridor == "IN>SG"
    assert route.amount == Decimal("25000")
    assert route.currency_from == "INR"
    assert route.currency_to == "SGD"
    assert route.simulated is True
    assert route.status is RouteStatus.UP
    assert route.blocked_reason is None
    assert route.rule_id is None


@pytest.mark.parametrize("purpose", ["rent", "tuition", ""])
def test_upi_paynow_is_blocked_with_reason_and_rule_for_other_purposes(purpose):
    route = _quote("IN>SG", amount="25000", purpose=purpose)[0]

    assert route.rail == "upi_paynow"
    assert route.status is RouteStatus.UP
    assert route.blocked_reason
    assert route.rule_id == "in_upi_paynow_purpose_001"


@pytest.mark.parametrize("corridor", ["SG>IN", "SG>US"])
def test_unknown_corridor_returns_no_routes(corridor):
    assert _quote(corridor) == []


def test_precheck_returns_the_fixed_result_for_enable_pix():
    router = FakeRouter()

    first = router.precheck("enable_pix", "sim_pix", {"nationality": "CN"})
    second = router.precheck("enable_pix", "sim_pix", {})

    assert isinstance(first, PrecheckResult)
    assert first == second
    assert first.action_kind == "enable_pix"
    assert first.provider == "sim_pix"
    assert first.documents_likely
    assert first.review_triggers


def test_precheck_results_do_not_share_state():
    router = FakeRouter()

    first = router.precheck("enable_pix", "sim_pix", {})
    first.documents_likely.append("tampered")

    assert "tampered" not in router.precheck("enable_pix", "sim_pix", {}).documents_likely


def test_precheck_for_an_unscripted_kind_returns_an_empty_result():
    result = FakeRouter().precheck("open_account", "wise", {})

    assert result == PrecheckResult(
        provider="wise",
        action_kind="open_account",
        documents_likely=[],
        review_triggers=[],
        ready=None,
        rule_ids=[],
    )


def test_sg_to_sg_returns_one_real_wise_route_in_singapore_dollars():
    routes = _quote("SG>SG", amount="300", purpose="emergency")

    assert [route.rail for route in routes] == ["wise"]
    route = routes[0]
    assert (route.currency_from, route.currency_to) == ("SGD", "SGD")
    assert route.amount == Decimal("300")
    assert route.simulated is False
    assert route.blocked_reason is None
    assert route.rate_source == "fixture"
