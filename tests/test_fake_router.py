import inspect
from decimal import Decimal

import pytest

from contracts.interfaces import Router
from contracts.schemas import PrecheckResult, RouteStatus
from rails.fake_router import UPI_PAYNOW_PURPOSE_RULE, FakeRouter


def _quote(corridor: str, amount: str = "1200", purpose: str = "rent"):
    return FakeRouter().quote(corridor, Decimal(amount), purpose, "normal")


def test_fake_router_implements_the_router():
    router = FakeRouter()

    assert isinstance(router, Router)
    assert not inspect.isabstract(FakeRouter)


def test_sg_to_br_returns_wise_and_sim_pix():
    routes = _quote("SG>BR")

    assert [route.rail for route in routes] == ["wise", "sim_pix"]
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


def test_wise_route_carries_its_fee_spread_and_arrival():
    wise = _quote("SG>BR")[0]

    assert wise.fee == Decimal("5.60")
    assert wise.spread_cost == Decimal("4.80")
    assert wise.arrival_hours == 24
    assert wise.simulated is False


def test_wise_spread_is_four_tenths_of_a_percent_of_the_amount():
    wise = _quote("SG>BR", amount="500")[0]

    assert wise.spread_cost == Decimal("2.00")


def test_sim_pix_route_is_simulated_and_arrives_in_an_hour():
    sim_pix = _quote("SG>BR")[1]

    assert sim_pix.simulated is True
    assert sim_pix.arrival_hours == 1


@pytest.mark.parametrize("purpose", ["allowance", "family_support"])
def test_sg_to_in_returns_one_open_upi_paynow_route(purpose):
    routes = _quote("SG>IN", amount="300", purpose=purpose)

    assert len(routes) == 1
    route = routes[0]
    assert route.rail == "upi_paynow"
    assert route.corridor == "SG>IN"
    assert route.currency_from == "SGD"
    assert route.currency_to == "INR"
    assert route.simulated is True
    assert route.status is RouteStatus.UP
    assert route.blocked_reason is None
    assert route.rule_id is None


@pytest.mark.parametrize("purpose", ["rent", "tuition", ""])
def test_upi_paynow_is_blocked_with_reason_and_rule_for_other_purposes(purpose):
    route = _quote("SG>IN", amount="300", purpose=purpose)[0]

    assert route.rail == "upi_paynow"
    assert route.status is RouteStatus.UP
    assert route.blocked_reason
    assert route.rule_id == UPI_PAYNOW_PURPOSE_RULE


def test_unknown_corridor_returns_no_routes():
    assert _quote("SG>US") == []


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


def test_precheck_refuses_an_unscripted_action_kind():
    with pytest.raises(ValueError, match="open_account"):
        FakeRouter().precheck("open_account", "wise", {})
