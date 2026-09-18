from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.schemas import Action, ActionType, Mandate, Source, Tier
from core.mandate import WARNING_KEYS, check
from core.tiers import TIERS


def _mandate(valid_from: datetime | None = None, valid_until: datetime | None = None) -> Mandate:
    now = datetime.now(timezone.utc)
    return Mandate(
        id="mandate-student_001-v1",
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
        valid_from=valid_from or now - timedelta(days=30),
        valid_until=valid_until or now + timedelta(days=30),
    )


def _expired_mandate() -> Mandate:
    return _mandate(valid_until=datetime.now(timezone.utc) - timedelta(days=1))


def test_transfer_over_per_txn_limit_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0001-test",
        amount=Decimal("1600"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R08" in decision.rule_ids


def test_transfer_to_unknown_payee_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0002-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="stranger_42",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R06" in decision.rule_ids


def test_transfer_on_disallowed_corridor_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0003-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>IN",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R05" in decision.rule_ids


def test_transfer_with_disallowed_purpose_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0004-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="crypto",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R07" in decision.rule_ids


def test_transfer_breaking_two_rules_reports_both():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0007-test",
        amount=Decimal("1600"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="stranger_42",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R06" in decision.rule_ids
    assert "R08" in decision.rule_ids
    assert len(decision.reasons) == 2


def test_transfer_in_wrong_currency_is_denied():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0005-test",
        amount=Decimal("1200"),
        currency="USD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert "R04" in decision.rule_ids


def test_transfer_within_mandate_is_allowed():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0006-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    decision = check(action, _mandate())

    assert decision.allowed is True
    assert decision.rule_ids == ["R11"]


def test_replayed_idempotency_key_is_refused_on_its_own():
    history = [_executed_today("txn-0200-done", "1400")]
    action = _executed_today("txn-0200-done", "1400")

    decision = check(action, _mandate(), history)

    assert decision.allowed is False
    assert decision.rule_ids == ["R10"]


def test_requested_at_defaults_to_an_aware_utc_timestamp():
    before = datetime.now(timezone.utc)
    action = Action(type=ActionType.READ_BALANCE, idempotency_key="txn-0008-test")
    after = datetime.now(timezone.utc)

    assert action.requested_at.utcoffset() == timedelta(0)
    assert before <= action.requested_at <= after

    with pytest.raises(ValidationError):
        Action(
            type=ActionType.READ_BALANCE,
            idempotency_key="txn-0009-test",
            requested_at=datetime(2026, 9, 14, 12, 0, 0),
        )


def _transfer_fields(**overrides) -> dict:
    fields = {
        "type": ActionType.TRANSFER,
        "idempotency_key": "txn-0600-test",
        "amount": Decimal("1200"),
        "currency": "SGD",
        "corridor": "SG>BR",
        "payee_id": "landlord_sp",
        "purpose": "rent",
    }
    fields.update(overrides)
    return fields


def test_negative_amount_is_rejected_by_the_schema():
    with pytest.raises(ValidationError):
        Action(**_transfer_fields(amount=Decimal("-5")))


def test_corridor_written_as_prose_is_rejected_by_the_schema():
    with pytest.raises(ValidationError):
        Action(**_transfer_fields(corridor="Singapore to Brazil"))


def test_short_idempotency_key_is_rejected_by_the_schema():
    with pytest.raises(ValidationError):
        Action(**_transfer_fields(idempotency_key="txn-1"))


def test_check_accepts_prior_history_without_changing_the_verdict():
    mandate = _mandate()
    earlier = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0010-test",
        amount=Decimal("400"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0011-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
    )

    assert check(action, mandate, [earlier]) == check(action, mandate)


def test_every_action_type_has_a_tier():
    assert set(TIERS) == set(ActionType)


def test_change_limit_is_refused_as_tier_three():
    action = Action(type=ActionType.CHANGE_LIMIT, idempotency_key="txn-0300-test")

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R02"]
    assert decision.tier is Tier.T3


def test_read_balance_is_allowed_under_an_expired_mandate():
    action = Action(type=ActionType.READ_BALANCE, idempotency_key="txn-0301-test")

    decision = check(action, _expired_mandate())

    assert decision.allowed is True
    assert decision.rule_ids == ["R02"]
    assert decision.tier is Tier.T0


def test_allowed_reminder_cites_r02_as_tier_one():
    action = Action(type=ActionType.SET_REMINDER, idempotency_key="txn-0303-test")

    decision = check(action, _mandate())

    assert decision.allowed is True
    assert decision.rule_ids == ["R02"]
    assert decision.tier is Tier.T1


def test_transfer_under_an_expired_mandate_is_refused():
    action = _executed_today("txn-0302-test", "1200")

    decision = check(action, _expired_mandate())

    assert decision.allowed is False
    assert "R03" in decision.rule_ids
    assert decision.tier is Tier.T2


def _executed_today(
    key: str, amount: str, confirmation_token: str | None = None
) -> Action:
    return Action(
        type=ActionType.TRANSFER,
        idempotency_key=key,
        amount=Decimal(amount),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
        confirmation_token=confirmation_token,
    )


def test_transfer_proposed_by_pasted_text_is_refused_on_its_own():
    action = Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0500-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
        source=Source.PASTED_TEXT,
    )

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R01"]


def test_source_defaults_to_the_user_turn():
    assert _executed_today("txn-0501-test", "1200").source is Source.USER_TURN


def test_transfer_without_a_token_is_allowed_but_needs_confirmation():
    action = _executed_today("txn-0400-test", "1200")

    decision = check(action, _mandate())

    assert decision.allowed is True
    assert decision.rule_ids == ["R11"]
    assert decision.requires_confirmation is True
    assert decision.tier is Tier.T2
    assert decision.warning_key == "warn.transfer.irreversible"
    assert decision.confirmation_token


def test_transfer_carrying_its_own_token_needs_no_further_confirmation():
    mandate = _mandate()
    token = check(_executed_today("txn-0401-test", "1200"), mandate).confirmation_token

    decision = check(_executed_today("txn-0401-test", "1200", token), mandate)

    assert decision.allowed is True
    assert decision.rule_ids == ["R11"]
    assert decision.requires_confirmation is False
    assert decision.warning_key == "warn.transfer.irreversible"
    assert decision.confirmation_token is None


def test_token_issued_for_one_amount_is_refused_on_another():
    mandate = _mandate()
    token = check(_executed_today("txn-0402-test", "1200"), mandate).confirmation_token

    decision = check(_executed_today("txn-0402-test", "1300", token), mandate)

    assert decision.allowed is False
    assert "R11" in decision.rule_ids


def test_transfer_over_daily_limit_with_history_is_denied():
    history = [_executed_today("txn-0100-earlier", "1400")]
    action = _executed_today("txn-0101-test", "1200")

    decision = check(action, _mandate(), history)

    assert decision.allowed is False
    assert "R09" in decision.rule_ids
    assert any("2600" in reason for reason in decision.reasons)


def test_transfer_within_daily_limit_with_history_is_allowed():
    history = [_executed_today("txn-0100-earlier", "1400")]
    action = _executed_today("txn-0102-test", "1000")

    decision = check(action, _mandate(), history)

    assert decision.allowed is True
    assert decision.rule_ids == ["R11"]


@pytest.mark.parametrize("missing", ["amount", "currency"])
def test_transfer_without_an_amount_or_a_currency_is_refused_under_r04(missing):
    action = Action(**_transfer_fields(idempotency_key="txn-0601-test", **{missing: None}))

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R04"]
    assert f"no {missing}" in decision.reasons[0]
    assert decision.requires_confirmation is False
    assert decision.confirmation_token is None


def test_every_t2_action_type_has_a_warning_key():
    assert set(WARNING_KEYS) == {kind for kind, tier in TIERS.items() if tier is Tier.T2}


def _t2_action(action_type: ActionType, payee_id: str | None = None, token: str | None = None) -> Action:
    return Action(
        type=action_type,
        idempotency_key="txn-0700-test",
        payee_id=payee_id,
        instrument_id="wise:card_01" if action_type is ActionType.FREEZE_CARD else None,
        confirmation_token=token,
    )


@pytest.mark.parametrize(
    ("action_type", "warning_key"),
    [
        (ActionType.ADD_PAYEE, "warn.payee.new"),
        (ActionType.FREEZE_CARD, "warn.freeze.card"),
    ],
)
def test_every_t2_action_needs_the_same_token_round_trip(action_type, warning_key):
    mandate = _mandate()

    first = check(_t2_action(action_type, "new_flatmate"), mandate)
    confirmed = check(_t2_action(action_type, "new_flatmate", first.confirmation_token), mandate)

    assert (first.allowed, first.requires_confirmation) == (True, True)
    assert first.rule_ids == ["R11"]
    assert first.warning_key == warning_key
    assert first.confirmation_token
    assert (confirmed.allowed, confirmed.requires_confirmation) == (True, False)
    assert confirmed.rule_ids == ["R11"]
    assert confirmed.warning_key == warning_key
    assert confirmed.confirmation_token is None


def test_token_issued_for_one_new_payee_is_refused_for_another():
    mandate = _mandate()
    token = check(_t2_action(ActionType.ADD_PAYEE, "new_flatmate"), mandate).confirmation_token

    decision = check(_t2_action(ActionType.ADD_PAYEE, "stranger_42", token), mandate)

    assert decision.allowed is False
    assert decision.rule_ids == ["R11"]


def test_freeze_token_for_one_instrument_is_refused_for_another():
    mandate = _mandate()
    first = Action(type=ActionType.FREEZE_CARD, idempotency_key="txn-0800-test", instrument_id="wise:card_01")
    token = check(first, mandate).confirmation_token

    other = first.model_copy(update={"instrument_id": "wise:card_02", "confirmation_token": token})
    same = first.model_copy(update={"confirmation_token": token})

    assert check(other, mandate).rule_ids == ["R11"]
    assert check(same, mandate).allowed is True


@pytest.mark.parametrize("payee_id", [None, ""])
def test_add_payee_without_a_payee_id_is_refused_under_r04(payee_id):
    action = Action(type=ActionType.ADD_PAYEE, idempotency_key="txn-0801-test", payee_id=payee_id)

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R04"]
    assert "payee id" in decision.reasons[0]
    assert decision.confirmation_token is None


def test_cooling_hours_default_to_24():
    assert _mandate().cooling_hours == 24
    assert _mandate().payee_added_at == {}


def _cooling_mandate(added_hours_ago: float) -> Mandate:
    mandate = _mandate()
    added_at = datetime.now(timezone.utc) - timedelta(hours=added_hours_ago)
    return mandate.model_copy(
        update={
            "allowed_payees": mandate.allowed_payees | {"new_flatmate"},
            "payee_added_at": {"new_flatmate": added_at},
        }
    )


def test_transfer_to_a_payee_inside_the_cooling_window_is_refused_under_r14():
    mandate = _cooling_mandate(added_hours_ago=2)
    allowed_from = mandate.payee_added_at["new_flatmate"] + timedelta(hours=24)

    decision = check(Action(**_transfer_fields(payee_id="new_flatmate")), mandate)

    assert decision.allowed is False
    assert decision.rule_ids == ["R14"]
    assert allowed_from.isoformat(timespec="seconds") in decision.reasons[0]


def test_transfer_to_a_payee_after_the_cooling_window_is_allowed():
    decision = check(Action(**_transfer_fields(payee_id="new_flatmate")), _cooling_mandate(added_hours_ago=25))

    assert decision.allowed is True
    assert decision.rule_ids == ["R11"]


def test_cooling_hours_can_be_set_per_mandate():
    mandate = _cooling_mandate(added_hours_ago=2).model_copy(update={"cooling_hours": 1})

    assert check(Action(**_transfer_fields(payee_id="new_flatmate")), mandate).allowed is True


@pytest.mark.parametrize("instrument_id", [None, ""])
def test_freeze_card_without_an_instrument_id_is_refused_under_r04(instrument_id):
    action = Action(type=ActionType.FREEZE_CARD, idempotency_key="txn-0802-test", instrument_id=instrument_id)

    decision = check(action, _mandate())

    assert decision.allowed is False
    assert decision.rule_ids == ["R04"]
    assert "card" in decision.reasons[0]
    assert decision.confirmation_token is None
