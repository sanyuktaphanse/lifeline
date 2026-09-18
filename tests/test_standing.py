from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.schemas import Action, ActionType, Mandate, Source, StandingMandate, StandingTerms, Tier
from core.mandate import WARNING_KEYS, check, confirmation_token_for
from core.standing import next_occurrence, occurrence_containing
from core.tiers import TIERS

NOW = datetime.now(timezone.utc)
STANDING_ID = "student_001-standing-1"


def _schedule_soon() -> tuple[str, datetime]:
    target = NOW + timedelta(days=5)
    day = target.day if target.day <= 28 else 1
    schedule = f"monthly:{day}"
    return schedule, next_occurrence(schedule, NOW + timedelta(days=1))[1]


SCHEDULE, DUE = _schedule_soon()
PERIOD = f"{DUE.year:04d}-{DUE.month:02d}"


def _standing(**overrides) -> StandingMandate:
    fields = {
        "id": STANDING_ID,
        "payee_id": "landlord_sp",
        "amount": Decimal("1200"),
        "tolerance_pct": Decimal("5"),
        "schedule": SCHEDULE,
        "corridor": "SG>BR",
        "purpose": "rent",
        "notice_hours": 48,
        "cancel_window_hours": 24,
        "confirmed_at": NOW - timedelta(days=1),
        "confirmation_token": "stored-token",
        "active": True,
    }
    fields.update(overrides)
    return StandingMandate(**fields)


def _mandate(*standing: StandingMandate) -> Mandate:
    return Mandate(
        id="mandate-student_001-v2",
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp", "joao_rio"},
        allowed_corridors={"SG>BR", "SG>IN"},
        allowed_purposes={"rent", "allowance"},
        valid_from=NOW - timedelta(days=30),
        valid_until=NOW + timedelta(days=60),
        standing_mandates=list(standing) or [_standing()],
    )


def _run(**overrides) -> Action:
    fields = {
        "type": ActionType.TRANSFER,
        "source": Source.STANDING_MANDATE,
        "idempotency_key": f"student_001:standing:{STANDING_ID}:{PERIOD}",
        "requested_at": DUE,
        "amount": Decimal("1200"),
        "currency": "SGD",
        "corridor": "SG>BR",
        "payee_id": "landlord_sp",
        "purpose": "rent",
        "standing_mandate_id": STANDING_ID,
    }
    fields.update(overrides)
    return Action(**fields)


def test_standing_action_types_have_their_tiers_and_warning():
    assert TIERS[ActionType.CREATE_STANDING_MANDATE] is Tier.T2
    assert TIERS[ActionType.CANCEL_STANDING_RUN] is Tier.T1
    assert WARNING_KEYS[ActionType.CREATE_STANDING_MANDATE] == "warn.standing.new"


def test_a_run_within_pattern_is_allowed_at_t1_under_r12_without_confirmation():
    decision = check(_run(), _mandate())

    assert decision.allowed is True
    assert decision.rule_ids == ["R12"]
    assert decision.tier is Tier.T1
    assert decision.requires_confirmation is False
    assert decision.confirmation_token is None
    assert decision.reasons == []


def test_the_student_may_also_send_the_run_themselves_within_pattern():
    decision = check(_run(source=Source.USER_TURN, idempotency_key="txn-standing-own"), _mandate())

    assert decision.rule_ids == ["R12"]


@pytest.mark.parametrize("amount", ["1140", "1260", "1200.50"])
def test_an_amount_inside_the_tolerance_is_within_pattern(amount):
    assert check(_run(amount=Decimal(amount)), _mandate()).rule_ids == ["R12"]


@pytest.mark.parametrize("hours", [-48, 0, 23])
def test_a_request_inside_the_schedule_window_is_within_pattern(hours):
    assert check(_run(requested_at=DUE + timedelta(hours=hours)), _mandate()).rule_ids == ["R12"]


def _escalated(action: Action, mandate: Mandate | None = None):
    decision = check(action.model_copy(update={"source": Source.USER_TURN}), mandate or _mandate())
    assert decision.allowed is True
    assert decision.rule_ids == ["R13", "R11"]
    assert decision.tier is Tier.T2
    assert decision.requires_confirmation is True
    assert decision.warning_key == "warn.transfer.irreversible"
    return decision.reasons[0]


def test_an_unknown_standing_mandate_escalates_under_r13():
    assert "no standing mandate standing-x" in _escalated(_run(standing_mandate_id="standing-x"))


@pytest.mark.parametrize("source", [Source.STANDING_MANDATE, Source.USER_TURN])
def test_a_run_under_an_inactive_standing_mandate_is_refused_under_r12(source):
    decision = check(_run(source=source), _mandate(_standing(active=False)))

    assert decision.allowed is False
    assert decision.rule_ids == ["R12"]
    assert "inactive" in decision.reasons[0]


def test_a_standing_mandate_confirmed_after_the_request_escalates_under_r13():
    late = _standing(confirmed_at=DUE + timedelta(hours=1))

    assert "confirmed after" in _escalated(_run(), _mandate(late))


def test_a_different_payee_escalates_under_r13_and_names_it():
    assert "payee joao_rio" in _escalated(_run(payee_id="joao_rio"))


def test_a_different_corridor_escalates_under_r13_and_names_it():
    assert "corridor SG>IN" in _escalated(_run(corridor="SG>IN"))


def test_a_different_purpose_escalates_under_r13_and_names_it():
    assert "purpose allowance" in _escalated(_run(purpose="allowance"))


@pytest.mark.parametrize("amount", ["1139.99", "1500"])
def test_an_amount_outside_the_tolerance_escalates_under_r13_and_names_it(amount):
    assert f"amount {amount}" in _escalated(_run(amount=Decimal(amount)))


@pytest.mark.parametrize("hours", [-49, 24, 24 * 10])
def test_a_request_outside_the_schedule_window_escalates_under_r13(hours):
    assert "outside the window" in _escalated(_run(requested_at=DUE + timedelta(hours=hours)))


def test_a_second_run_in_the_same_period_escalates_under_r13():
    executed = _run()
    second = _run(idempotency_key="txn-standing-second", requested_at=DUE + timedelta(hours=1))

    decision = check(second.model_copy(update={"source": Source.USER_TURN}), _mandate(), [executed])

    assert decision.rule_ids == ["R13", "R11"]
    assert f"a run for {PERIOD} already executed" in decision.reasons[0]


def test_every_reason_outside_the_pattern_is_named_in_one_r13_reason():
    reason = _escalated(_run(amount=Decimal("1500"), purpose="allowance"))

    assert "amount 1500" in reason and "purpose allowance" in reason


def test_an_escalated_transfer_that_breaks_a_money_rule_is_refused_citing_r13_too():
    decision = check(_run(source=Source.USER_TURN, payee_id="stranger_42"), _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R13", "R06"]


def test_a_run_within_pattern_still_passes_the_money_rules():
    tight = _mandate().model_copy(update={"per_txn_limit": Decimal("1000")})

    decision = check(_run(), tight)

    assert decision.allowed is False
    assert "R08" in decision.rule_ids


def test_the_standing_source_is_refused_under_r01_without_a_matching_standing_mandate():
    decision = check(_run(standing_mandate_id="standing-x"), _mandate())

    assert decision.rule_ids == ["R01"]


def test_the_standing_source_is_refused_under_r01_on_any_other_action():
    action = Action(type=ActionType.ADD_PAYEE, source=Source.STANDING_MANDATE, idempotency_key="txn-sm-0001", payee_id="x")

    assert check(action, _mandate()).rule_ids == ["R01"]


def _terms(**overrides) -> StandingTerms:
    fields = {"schedule": SCHEDULE, "tolerance_pct": Decimal("5"), "notice_hours": 48, "cancel_window_hours": 24}
    fields.update(overrides)
    return StandingTerms(**fields)


def _create(**overrides) -> Action:
    fields = {
        "type": ActionType.CREATE_STANDING_MANDATE,
        "idempotency_key": "student_001:t1:create_standing_mandate:1",
        "amount": Decimal("1200"),
        "currency": "SGD",
        "corridor": "SG>BR",
        "payee_id": "landlord_sp",
        "purpose": "rent",
        "standing_mandate_id": STANDING_ID,
        "standing_terms": _terms(),
    }
    fields.update(overrides)
    return Action(**fields)


def test_creating_a_standing_mandate_needs_confirmation_with_its_warning():
    decision = check(_create(), _mandate())

    assert (decision.allowed, decision.requires_confirmation) == (True, True)
    assert decision.rule_ids == ["R11"]
    assert decision.warning_key == "warn.standing.new"


@pytest.mark.parametrize("missing", ["amount", "payee_id", "standing_terms", "standing_mandate_id"])
def test_creating_a_standing_mandate_without_its_terms_is_refused_under_r04(missing):
    decision = check(_create(**{missing: None}), _mandate())

    assert decision.allowed is False
    assert "R04" in decision.rule_ids


def test_creating_a_standing_mandate_passes_the_payee_and_limit_rules():
    decision = check(_create(payee_id="stranger_42", amount=Decimal("1600")), _mandate())

    assert decision.allowed is False
    assert {"R06", "R08"} <= set(decision.rule_ids)


def test_the_token_signs_the_standing_terms():
    mandate = _mandate()
    token = confirmation_token_for(_create(), mandate)

    changed = _create(standing_terms=_terms(tolerance_pct=Decimal("50")), confirmation_token=token)

    assert check(changed, mandate).rule_ids == ["R11"]
    assert check(_create(confirmation_token=token), mandate).allowed is True


def test_cancelling_a_run_is_t1_and_needs_a_standing_mandate_on_the_mandate():
    cancel = Action(type=ActionType.CANCEL_STANDING_RUN, idempotency_key="txn-cancel-01", standing_mandate_id=STANDING_ID)

    allowed = check(cancel, _mandate())
    unknown = check(cancel.model_copy(update={"standing_mandate_id": "standing-x"}), _mandate())
    missing = check(cancel.model_copy(update={"standing_mandate_id": None}), _mandate())

    assert (allowed.allowed, allowed.tier, allowed.rule_ids, allowed.requires_confirmation) == (True, Tier.T1, ["R02"], False)
    assert unknown.rule_ids == ["R04"]
    assert missing.rule_ids == ["R04"]


@pytest.mark.parametrize("schedule", ["monthly:0", "monthly:29", "weekly:1", "1st of the month"])
def test_a_schedule_must_be_monthly_on_a_day_from_1_to_28(schedule):
    with pytest.raises(ValidationError):
        _terms(schedule=schedule)


def test_the_cancel_window_may_not_exceed_the_notice():
    with pytest.raises(ValidationError):
        _terms(notice_hours=24, cancel_window_hours=25)


def test_occurrences_follow_the_window_around_each_due_date():
    schedule = "monthly:10"
    due = datetime(2026, 10, 10, tzinfo=timezone.utc)

    assert occurrence_containing(schedule, 48, due - timedelta(hours=48)) == ("2026-10", due)
    assert occurrence_containing(schedule, 48, due + timedelta(hours=23, minutes=59)) == ("2026-10", due)
    assert occurrence_containing(schedule, 48, due - timedelta(hours=49)) is None
    assert occurrence_containing(schedule, 48, due + timedelta(hours=24)) is None
    assert next_occurrence(schedule, due + timedelta(hours=24)) == ("2026-11", datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert next_occurrence("monthly:1", datetime(2026, 12, 20, tzinfo=timezone.utc)) == ("2027-01", datetime(2027, 1, 1, tzinfo=timezone.utc))



def test_deactivating_is_t1_and_needs_a_standing_mandate_on_the_mandate():
    deactivate = Action(type=ActionType.DEACTIVATE_STANDING_MANDATE, idempotency_key="txn-deact-01", standing_mandate_id=STANDING_ID)

    allowed = check(deactivate, _mandate())
    unknown = check(deactivate.model_copy(update={"standing_mandate_id": "standing-x"}), _mandate())

    assert TIERS[ActionType.DEACTIVATE_STANDING_MANDATE] is Tier.T1
    assert (allowed.allowed, allowed.rule_ids, allowed.requires_confirmation) == (True, ["R02"], False)
    assert unknown.rule_ids == ["R04"]
