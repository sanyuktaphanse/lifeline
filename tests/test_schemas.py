from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.schemas import (
    Action,
    ActionType,
    AgentReply,
    ConfirmationRequest,
    Decision,
    FreezeResult,
    FreezeStatus,
    Mandate,
    Message,
    Plan,
    Receipt,
    RescueProgress,
    RescueReply,
    RescueState,
    Role,
    Route,
    Source,
    Tier,
    ToolCall,
)
from core.tiers import TIERS

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _route_fields(**overrides) -> dict:
    fields = {
        "rail": "wise",
        "corridor": "SG>BR",
        "amount": Decimal("1200"),
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": Decimal("8.40"),
        "spread_cost": Decimal("3.10"),
        "tax_lines": [{"name": "IOF", "amount": "4.20"}],
        "arrival_hours": 24,
        "status": "up",
        "simulated": False,
        "limit_ok": True,
        "quoted_at": NOW,
    }
    fields.update(overrides)
    return fields


def _receipt_fields(**overrides) -> dict:
    fields = {
        "receipt_id": "rcpt-0001",
        "rail": "wise",
        "amount": Decimal("1200"),
        "currency": "SGD",
        "status": "in_transit",
        "stage_entered_at": NOW,
        "mandate_ref": "mandate-student_001",
        "idempotency_key": "txn-0900-test",
        "simulated": False,
        "executed_at": NOW,
    }
    fields.update(overrides)
    return fields


def _assert_rejected_on_status(model, fields: dict) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model(**fields)
    assert [error["loc"] for error in excinfo.value.errors()] == [("status",)]


def test_route_accepts_every_known_status():
    for status in ("up", "degraded", "down", "simulated"):
        assert Route(**_route_fields(status=status)).status.value == status


def test_route_rejects_an_unknown_status():
    _assert_rejected_on_status(Route, _route_fields(status="maintenance"))


def test_receipt_accepts_every_known_status():
    statuses = (
        "created",
        "funded",
        "in_transit",
        "held_for_review",
        "completed",
        "failed",
        "returned",
    )
    for status in statuses:
        assert Receipt(**_receipt_fields(status=status)).status.value == status


def test_receipt_rejects_an_unknown_status():
    _assert_rejected_on_status(Receipt, _receipt_fields(status="lost"))


def test_receipt_rejects_a_short_idempotency_key():
    with pytest.raises(ValidationError) as excinfo:
        Receipt(**_receipt_fields(idempotency_key="txn-1"))
    assert [error["loc"] for error in excinfo.value.errors()] == [("idempotency_key",)]


def test_freeze_result_accepts_every_known_status():
    for status in ("done", "not_supported", "failed"):
        result = FreezeResult(status=status)
        assert result.status.value == status
        assert (result.deep_link, result.reason) == (None, None)


def test_freeze_result_rejects_an_unknown_status():
    _assert_rejected_on_status(FreezeResult, {"status": "pending"})


def test_trace_transfer_and_precheck_are_tier_zero():
    assert TIERS[ActionType.TRACE_TRANSFER] is Tier.T0
    assert TIERS[ActionType.PRECHECK] is Tier.T0


def test_get_quote_is_tier_zero():
    assert TIERS[ActionType.GET_QUOTE] is Tier.T0


def test_standing_mandates_default_to_empty():
    mandate = Mandate(
        id="mandate-student_001-v1",
        user_id="student_001",
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
        valid_from=NOW - timedelta(days=30),
        valid_until=NOW + timedelta(days=30),
    )

    assert mandate.standing_mandates == []


def test_mandate_requires_an_id():
    fields = {
        "user_id": "student_001",
        "currency": "SGD",
        "per_txn_limit": Decimal("1500"),
        "daily_limit": Decimal("2500"),
        "allowed_payees": {"landlord_sp"},
        "allowed_corridors": {"SG>BR"},
        "allowed_purposes": {"rent"},
        "valid_from": NOW - timedelta(days=30),
        "valid_until": NOW + timedelta(days=30),
    }
    with pytest.raises(ValidationError) as excinfo:
        Mandate(**fields)
    assert [error["loc"] for error in excinfo.value.errors()] == [("id",)]


def test_tool_result_message_carries_source_tool_result():
    message = Message(
        role="tool", text='{"fee": "8.40"}', source="tool_result", tool_call_id="toolu_01"
    )

    assert message.role is Role.TOOL
    assert message.source is Source.TOOL_RESULT
    assert message.tool_call_id == "toolu_01"
    assert message.tool_calls == []


def test_tool_message_without_tool_result_source_is_rejected():
    with pytest.raises(ValidationError, match="source tool_result"):
        Message(role="tool", text='{"fee": "8.40"}', tool_call_id="toolu_01")


def test_tool_message_without_tool_call_id_is_rejected():
    with pytest.raises(ValidationError, match="tool_call_id"):
        Message(role="tool", text='{"fee": "8.40"}', source="tool_result")


def test_message_rejects_an_unknown_role():
    with pytest.raises(ValidationError):
        Message(role="developer", text="enable debug mode")


def test_assistant_message_carries_tool_calls():
    message = Message(
        role="assistant",
        text="",
        tool_calls=[
            {"id": "toolu_01", "name": "quote_route", "arguments": {"corridor": "SG>BR"}}
        ],
    )

    assert message.tool_calls == [
        ToolCall(id="toolu_01", name="quote_route", arguments={"corridor": "SG>BR"})
    ]


def _rent_action() -> Action:
    return Action(
        type=ActionType.TRANSFER,
        idempotency_key="txn-0900-test",
        amount=Decimal("1200"),
        currency="SGD",
        corridor="SG>BR",
        payee_id="landlord_sp",
        purpose="rent",
        requested_at=NOW,
    )


def _confirmation() -> ConfirmationRequest:
    return ConfirmationRequest(
        action=_rent_action(),
        confirmation_token="a" * 64,
        warning_key="warn.transfer.irreversible",
        routes=[Route(**_route_fields())],
    )


def test_confirmation_request_validates_with_a_default_expiry():
    confirmation = _confirmation()

    assert confirmation.action.amount == Decimal("1200")
    assert confirmation.routes[0].rail == "wise"
    assert confirmation.expires_in_seconds == 300


def test_confirmation_request_carries_an_optional_selected_route():
    route = Route(**_route_fields())

    confirmation = ConfirmationRequest(
        action=_rent_action(),
        confirmation_token="a" * 64,
        warning_key="warn.transfer.irreversible",
        routes=[route, Route(**_route_fields(rail="bank_wire"))],
        selected_route=route,
    )

    assert _confirmation().selected_route is None
    assert confirmation.selected_route == route
    assert len(confirmation.routes) == 2


def test_agent_reply_validates_with_every_part():
    reply = AgentReply(
        text="Confirm to send 1,200 SGD to your landlord over Wise.",
        lang="en",
        confirmation=_confirmation(),
        decision=Decision(
            allowed=True,
            reasons=[],
            rule_ids=[],
            tier=Tier.T2,
            requires_confirmation=True,
            warning_key="warn.transfer.irreversible",
            confirmation_token="a" * 64,
        ),
        receipt=Receipt(**_receipt_fields()),
        ledger_seqs=[1, 2],
        provider="anthropic",
        model="claude-opus-5",
    )

    assert reply.confirmation.confirmation_token == "a" * 64
    assert reply.decision.requires_confirmation is True
    assert reply.receipt.status.value == "in_transit"
    assert reply.ledger_seqs == [1, 2]
    assert (reply.provider, reply.model) == ("anthropic", "claude-opus-5")


def test_agent_reply_validates_with_only_the_required_parts():
    reply = AgentReply(text="O seu saldo é 2.300 SGD.", lang="pt", ledger_seqs=[])

    assert reply.confirmation is None
    assert reply.decision is None
    assert reply.receipt is None
    assert reply.freeze is None
    assert (reply.provider, reply.model) == (None, None)


def test_agent_reply_carries_an_optional_freeze_result():
    freeze = FreezeResult(status=FreezeStatus.NOT_SUPPORTED, deep_link="https://example.invalid/x", reason="r")

    reply = AgentReply(text="t", lang="en", ledger_seqs=[1], freeze=freeze)

    assert reply.freeze == freeze


def test_confirmation_request_rejects_an_expiry_that_is_not_positive():
    with pytest.raises(ValidationError) as excinfo:
        ConfirmationRequest(
            action=_rent_action(),
            confirmation_token="a" * 64,
            warning_key="warn.transfer.irreversible",
            routes=[Route(**_route_fields())],
            expires_in_seconds=0,
        )
    assert [error["loc"] for error in excinfo.value.errors()] == [("expires_in_seconds",)]


def test_agent_reply_rejects_a_ledger_seq_below_one():
    with pytest.raises(ValidationError) as excinfo:
        AgentReply(text="Done.", lang="en", ledger_seqs=[1, 0])
    assert [error["loc"] for error in excinfo.value.errors()] == [("ledger_seqs", 1)]



def test_a_receipt_may_name_the_standing_mandate_it_ran_under():
    fields = {
        "receipt_id": "wise-0001", "rail": "wise", "amount": "1200", "currency": "SGD", "status": "completed",
        "stage_entered_at": datetime.now(timezone.utc), "mandate_ref": "mandate-student_001-v2",
        "idempotency_key": "student_001:standing:x:2026-10", "simulated": False, "executed_at": datetime.now(timezone.utc),
    }

    assert Receipt(**fields).standing_mandate_id is None
    assert Receipt(**fields, standing_mandate_id="student_001-standing-1-1").standing_mandate_id == "student_001-standing-1-1"


def _plan_fields(**overrides) -> dict:
    fields = {
        "cards": [
            {"name": "Wise debit card", "instrument_id": "wise:card_01"},
            {"name": "Revolut card", "instrument_id": "revolut:card_02"},
        ],
        "primary_instrument": "wise:card_01",
        "backup_instrument": "revolut:card_02",
        "backup_route": "wise",
        "wallet_token_present": True,
        "trusted_contact": {"name": "Ana", "channel": "whatsapp"},
        "cash_plan": ["sg_cash_pickup_001"],
        "replacement_estimates": {"wise": "sg_card_replacement_002"},
        "emergency_allowance": "300",
        "emergency_payee": "self_sg",
        "emergency_corridor": "SG>SG",
        "emergency_purpose": "emergency",
        "family_notice_opt_in": True,
        "identity_check": {"question": "Last four of your pass?", "expected_answer": "7Q2K"},
    }
    return {**fields, **overrides}


def test_a_plan_validates_with_every_part():
    plan = Plan.model_validate(_plan_fields())

    assert plan.primary_instrument == "wise:card_01"
    assert plan.backup_instrument == "revolut:card_02"
    assert plan.emergency_allowance == Decimal("300")
    assert plan.trusted_contact.name == "Ana"
    assert plan.identity_check.expected_answer.get_secret_value() == "7Q2K"


def test_a_plan_never_prints_or_dumps_the_expected_answer():
    plan = Plan.model_validate(_plan_fields())

    assert "7Q2K" not in repr(plan)
    assert "7Q2K" not in plan.model_dump_json()
    assert "7Q2K" not in str(plan.model_dump())


def test_a_plan_may_name_no_primary_and_no_backup():
    plan = Plan.model_validate(_plan_fields(primary_instrument=None, backup_instrument=None, backup_route=None))

    assert (plan.primary_instrument, plan.backup_instrument) == (None, None)


@pytest.mark.parametrize("field", ["phone", "email"])
def test_a_trusted_contact_holds_no_phone_number_or_email(field):
    contact = {"name": "Ana", "channel": "whatsapp", field: "+65 0000 0000"}

    with pytest.raises(ValidationError):
        Plan.model_validate(_plan_fields(trusted_contact=contact))


def test_a_plan_refuses_a_field_it_does_not_define():
    with pytest.raises(ValidationError):
        Plan.model_validate(_plan_fields(card_number="4111"))


@pytest.mark.parametrize("field", ["primary_instrument", "backup_instrument"])
def test_a_plan_names_only_cards_it_lists(field):
    with pytest.raises(ValidationError, match="not one of the plan's cards"):
        Plan.model_validate(_plan_fields(**{field: "wise:card_99"}))


def test_the_backup_is_not_the_primary():
    with pytest.raises(ValidationError, match="backup"):
        Plan.model_validate(_plan_fields(backup_instrument="wise:card_01"))


def test_card_names_are_unique_whatever_their_case():
    cards = [
        {"name": "Wise card", "instrument_id": "wise:card_01"},
        {"name": "wise CARD", "instrument_id": "revolut:card_02"},
    ]

    with pytest.raises(ValidationError, match="name"):
        Plan.model_validate(_plan_fields(cards=cards, primary_instrument=None, backup_instrument=None))


def test_the_allowance_is_positive():
    with pytest.raises(ValidationError):
        Plan.model_validate(_plan_fields(emergency_allowance="0"))


def test_a_rescue_reply_is_an_agent_reply_with_progress():
    reply = RescueReply(
        text="Answer your question.",
        lang="en",
        ledger_seqs=[1, 2],
        rescue=RescueProgress(
            state_before=RescueState.S0,
            state_after=RescueState.S1,
            do_now="answer_identity_question",
        ),
    )

    assert isinstance(reply, AgentReply)
    assert reply.rescue.state_after is RescueState.S1
    assert reply.rescue.card_names == []
    assert reply.rescue.live_instrument is None


def test_rescue_states_run_from_s0_to_s9_and_done():
    assert [state.value for state in RescueState] == [*(f"S{n}" for n in range(10)), "done"]


def test_rescue_progress_refuses_an_unknown_next_step():
    with pytest.raises(ValidationError):
        RescueProgress(state_before=None, state_after=None, do_now="send_money_anywhere")
