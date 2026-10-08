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
        assert route.purpose == "rent"
        assert route.payee_id is None
        assert route.quoted_at.tzinfo is not None
    assert [route.rule_id for route in routes] == [None, "br_pix_instant_001", None]
    assert all(route.fee_source_url is None for route in routes)


def test_wise_route_has_its_fee_and_no_spread():
    wise = _by_rail(_quote("SG>BR"))["wise"]

    assert wise.fee == Decimal("5.60")
    assert wise.spread_cost == Decimal("0")
    assert wise.arrival_hours == 24
    assert wise.simulated is False


def test_sim_pix_route_is_simulated_and_arrives_when_the_entry_it_cites_says():
    from rails.knowledge.loader import load_knowledge

    sim_pix = _by_rail(_quote("SG>BR"))["sim_pix"]

    assert sim_pix.simulated is True
    assert sim_pix.rule_id == "br_pix_instant_001"
    assert sim_pix.arrival_hours == load_knowledge()["br_pix_instant_001"]["values"]["typical_duration_hours"]


def test_bank_wire_route_has_its_fee_spread_and_arrival():
    bank_wire = _by_rail(_quote("SG>BR"))["bank_wire"]

    assert bank_wire.fee == Decimal("25")
    assert bank_wire.spread_cost == Decimal("30.00")
    assert bank_wire.arrival_hours == 72
    assert bank_wire.simulated is False


def test_bank_wire_spread_is_two_and_a_half_percent_of_the_amount():
    bank_wire = _by_rail(_quote("SG>BR", amount="500"))["bank_wire"]

    assert bank_wire.spread_cost == Decimal("12.50")


@pytest.mark.parametrize("purpose", ["maintenance_of_relatives_abroad", "gift"])
def test_in_to_sg_returns_one_open_upi_paynow_route_for_the_rbi_purposes(purpose):
    routes = _quote("IN>SG", amount="25000", purpose=purpose)

    assert len(routes) == 1
    route = routes[0]
    assert route.rail == "upi_paynow_sim"
    assert route.corridor == "IN>SG"
    assert route.amount == Decimal("25000")
    assert (route.currency_from, route.currency_to) == ("INR", "SGD")
    assert route.simulated is True
    assert route.status is RouteStatus.UP
    assert route.blocked_reason is None
    assert route.rule_id == "in_upi_paynow_purpose_001"
    assert route.purpose == purpose
    assert route.fee_source_url is None
    assert route.rate_source == "fixture"


@pytest.mark.parametrize("purpose", ["business", "rent", "allowance", "tuition", ""])
def test_upi_paynow_is_blocked_for_any_other_purpose_naming_the_permitted_ones_and_the_entry(purpose):
    route = _quote("IN>SG", amount="25000", purpose=purpose)[0]

    assert route.rail == "upi_paynow_sim"
    assert route.rule_id == "in_upi_paynow_purpose_001"
    assert "maintenance_of_relatives_abroad" in route.blocked_reason
    assert "gift" in route.blocked_reason
    assert "in_upi_paynow_purpose_001" in route.blocked_reason
    assert repr(purpose) in route.blocked_reason


def test_upi_paynow_is_open_at_the_daily_cap_and_blocked_above_it_citing_the_cap_entry():
    at_cap = _quote("IN>SG", amount="60000", purpose="gift")[0]
    above = _quote("IN>SG", amount="60000.01", purpose="gift")[0]

    assert at_cap.blocked_reason is None
    assert above.rule_id == "in_upi_paynow_cap_002"
    assert "in_upi_paynow_cap_002" in above.blocked_reason
    assert "60000 INR" in above.blocked_reason
    assert above.limit_ok is False


def test_a_wrong_purpose_above_the_cap_names_both_entries():
    route = _quote("IN>SG", amount="70000", purpose="business")[0]

    assert route.rule_id == "in_upi_paynow_purpose_001"
    assert "in_upi_paynow_purpose_001" in route.blocked_reason
    assert "in_upi_paynow_cap_002" in route.blocked_reason


def test_cn_to_sg_tuition_is_blocked_because_nus_asks_for_flywire_or_convera():
    route = _quote("CN>SG", amount="30000", purpose="tuition")[0]

    assert route.rail == "cn_bank_remit_sim"
    assert (route.currency_from, route.currency_to) == ("CNY", "SGD")
    assert route.simulated is True
    assert route.rule_id == "sg_nus_fee_payment_003"
    for text in ("Flywire", "Convera", "no sourced rule", "direct bank remittance", "sg_nus_fee_payment_003", "cn_edu_remit_002"):
        assert text in route.blocked_reason


def test_cn_to_sg_funding_the_student_is_blocked_for_want_of_a_sourced_duration():
    route = _quote("CN>SG", amount="30000", purpose="living_costs")[0]

    assert route.rule_id == "cn_boc_anxin_009"
    assert "no sourced duration" in route.blocked_reason
    assert "cn_boc_anxin_009" in route.blocked_reason


def test_cn_to_sg_for_any_other_purpose_is_blocked_with_no_sourced_rule():
    route = _quote("CN>SG", amount="30000", purpose="rent")[0]

    assert "no sourced rule" in route.blocked_reason
    assert "'rent'" in route.blocked_reason


def test_the_china_precheck_gives_the_bank_of_china_checklist_and_the_chinese_side_rules():
    from rails.knowledge.loader import load_knowledge

    entries = load_knowledge()
    result = FakeRouter().precheck("remit_from_china", "cn_bank_remit_sim", {})

    assert result.documents_likely == entries["cn_boc_anxin_009"]["values"]["documents"]
    assert entries["cn_fx_quota_001"]["statement"] in result.review_triggers
    assert entries["cn_cdd_004"]["statement"] in result.review_triggers
    assert any("no sourced duration" in t and "cn_boc_anxin_009" in t for t in result.review_triggers)
    assert result.rule_ids == ["cn_boc_anxin_009", "cn_fx_quota_001", "cn_cdd_004"]
    assert result.ready is None


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
