import inspect
import json

from contracts.interfaces import Council, Ledger, MandateEngine, Rail, Router
from contracts.schemas import RouteStatus
from core.agent import MAX_MODEL_CALLS_PER_TURN, RUNNER_UP_DISAGREEMENT, AgentLoop
from core.council import NO_ANSWER, VOICES, WAIT, FiveVoiceCouncil, reason_for
from core.fake_adapter import FakeModelAdapter
from rails.fake_router import FakeRouter
from tests.test_agent import RENT, RENT_REQUEST, USER, Setup, _call, _kinds, _say, _setup, _user

WISE_REASON = "Wise costs the least of the routes that can carry this rent."
WIRE_REASON = "The bank wire is the route this landlord has been paid over before."
WAIT_REASON = "Waiting until tomorrow costs nothing and the rent is not due yet."
CONFIRM_TEXT = (
    "Please confirm: send 1200 SGD to landlord_sp for rent over wise, fee 5.60 SGD "
    "and exchange cost 0 SGD. Nothing moves until you confirm."
)
COUNCIL_SENTENCE = "The council chose wise."
RUNNER_UP_SENTENCE = "The council was divided. The next choice was bank_wire."
WAIT_SENTENCE = "The council advised waiting."
SMALL = {**RENT, "amount": "700"}
OTHER_PAYEE = {**RENT, "payee_id": "landlord_two"}
OVER_LIMIT = {**RENT, "amount": "3000"}


def _voice(position: str, confidence: float, reason: str, evidence=("wise",)) -> str:
    return json.dumps(
        {"position": position, "confidence": confidence, "reason": reason, "evidence": list(evidence)}
    )


def _split(*positions: tuple[str, float, str]) -> list[str]:
    """One scripted reply per voice, in the order cost, speed, safety, rules, timing."""
    assert len(positions) == len(VOICES)
    return [_voice(*position) for position in positions]


THREE_TWO = _split(
    ("wise", 0.9, WISE_REASON),
    ("wise", 0.8, WISE_REASON),
    ("wise", 0.7, WISE_REASON),
    ("bank_wire", 0.6, WIRE_REASON),
    ("bank_wire", 0.5, WIRE_REASON),
)
TWO_TWO_WAIT = _split(
    ("wise", 0.9, WISE_REASON),
    ("wise", 0.8, WISE_REASON),
    ("bank_wire", 0.6, WIRE_REASON),
    ("bank_wire", 0.5, WIRE_REASON),
    (WAIT, 0.4, WAIT_REASON),
)
ALL_WISE = _split(*[("wise", 0.8, WISE_REASON)] * len(VOICES))
ALL_WAIT = _split(*[(WAIT, 0.8, WAIT_REASON)] * len(VOICES))
ABSTAINING = "I would rather explain this in prose than in JSON."
THREE_ONE_ABSTAIN = [
    _voice("wise", 0.9, WISE_REASON),
    _voice("wise", 0.8, WISE_REASON),
    _voice("wise", 0.7, WISE_REASON),
    _voice("bank_wire", 0.6, WIRE_REASON),
    ABSTAINING,
]
NONE_VALID = [ABSTAINING] * len(VOICES)
UNUSABLE_RAIL = _split(*[("revolut", 0.9, WISE_REASON)] * len(VOICES))


class SlowCheapRouter(FakeRouter):
    """A router whose cheapest route is not its fastest, which the fixture router never gives."""

    def quote(self, corridor, amount, purpose, urgency):
        routes = super().quote(corridor, amount, purpose, urgency)
        return [
            route.model_copy(update={"arrival_hours": 96}) if route.rail == "sim_pix" else route
            for route in routes
        ]


class DegradedRouter(FakeRouter):
    """A router that marks one candidate degraded, which the fixture router never does."""

    def quote(self, corridor, amount, purpose, urgency):
        routes = super().quote(corridor, amount, purpose, urgency)
        return [
            route.model_copy(update={"status": RouteStatus.DEGRADED}) if route.rail == "bank_wire" else route
            for route in routes
        ]


def _council(replies: list[str]) -> FiveVoiceCouncil:
    return FiveVoiceCouncil(FakeModelAdapter(replies))


def _rent(replies: list[str] = THREE_TWO, *, arguments: dict | None = None, **overrides) -> Setup:
    return _setup(
        [_call("propose_transfer", RENT if arguments is None else arguments)],
        council=_council(replies),
        **overrides,
    )


def _entry(setup: Setup) -> dict:
    return next(entry.payload for entry in setup.ledger.entries() if entry.kind == "council")


def _advice(setup: Setup) -> dict:
    return _entry(setup)["council"]


def _councils(setup: Setup) -> list[dict]:
    return [entry.payload for entry in setup.ledger.entries() if entry.kind == "council"]


def _triggers(*, arguments: dict | None = None, **overrides) -> list[str]:
    setup = _rent(arguments=arguments, **overrides)
    setup.loop.handle(USER, _user(RENT_REQUEST))
    return _advice(setup)["triggers"]


def _paid_rent(replies: list[str], *, then=None) -> Setup:
    """Pay the rent once, so the corridor and the payee are no longer new to the history."""
    responses = [_call("propose_transfer", RENT)] + ([] if then is None else [then])
    setup = _setup(responses, council=_council(replies))
    token = setup.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    setup.loop.handle(USER, _user("Yes, send it"), confirmation_token=token)
    return setup


# The council is convened, and what it advises


def test_an_escalated_transfer_writes_one_council_entry_after_the_decision():
    s = _rent()

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert _kinds(s.ledger) == ["proposal", "decision", "council"]
    assert reply.confirmation is not None
    assert reply.confirmation.selected_route.rail == "wise"
    advice = _advice(s)
    assert advice["chosen"] == "wise"
    assert advice["runner_up"] == "bank_wire"
    assert advice["reason"] == " ".join([WISE_REASON] * 3)
    assert advice["question"]
    assert [voice["voice"] for voice in advice["voices"]] == list(VOICES)
    assert advice.keys() == {
        "chosen", "runner_up", "reason", "disagreement", "triggers", "voices", "question"
    }
    assert _entry(s)["idempotency_key"] == reply.confirmation.action.idempotency_key


def test_the_confirmation_carries_the_advice_as_data():
    s = _rent()

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    council = reply.confirmation.council
    assert council is not None
    assert (council.chosen, council.runner_up) == ("wise", "bank_wire")
    assert council.reason == " ".join([WISE_REASON] * 3)
    assert council.disagreement == RUNNER_UP_DISAGREEMENT
    assert "above_half_per_txn_limit" in council.triggers
    assert council.model_dump().keys() == {"chosen", "runner_up", "reason", "disagreement", "triggers"}


def test_the_reply_names_the_chosen_rail_and_its_reason():
    s = _rent()

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert reply.text == f"{CONFIRM_TEXT} {COUNCIL_SENTENCE} {' '.join([WISE_REASON] * 3)}"


def test_the_advice_reaches_the_model_as_the_tool_result_of_the_proposal():
    s = _setup(
        [_call("propose_transfer", RENT), _say("The council chose Wise because it costs the least.")],
        council=_council(THREE_TWO),
    )
    s.loop.handle(USER, _user(RENT_REQUEST))

    s.loop.handle(USER, _user("Why did the council choose that route?"))

    remembered = "\n".join(message.text for message in s.adapter.calls[-1][0])
    assert WISE_REASON in remembered
    assert '"chosen": "wise"' in remembered


def test_the_council_chooses_the_route_the_loop_then_selects():
    s = _rent(TWO_TWO_WAIT, router=SlowCheapRouter())

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert _advice(s)["chosen"] == "wise"
    assert reply.confirmation.selected_route.rail == "wise"


# Each escalation trigger, firing and not firing


def test_an_amount_above_half_the_per_transaction_limit_fires():
    assert "above_half_per_txn_limit" in _triggers()


def test_an_amount_at_or_below_half_the_per_transaction_limit_does_not_fire():
    assert "above_half_per_txn_limit" not in _triggers(arguments=SMALL)


def test_a_first_transfer_on_the_corridor_fires():
    assert "first_transfer_on_corridor" in _triggers()


def test_a_corridor_the_student_has_already_paid_over_does_not_fire():
    s = _paid_rent(THREE_TWO * 2, then=_call("propose_transfer", RENT, call_id="toolu_02"))

    s.loop.handle(USER, _user(RENT_REQUEST))

    assert "first_transfer_on_corridor" not in _councils(s)[-1]["council"]["triggers"]


def test_a_first_transfer_to_the_payee_fires():
    assert "first_transfer_to_payee" in _triggers()


def test_a_payee_the_student_has_already_paid_does_not_fire():
    s = _paid_rent(THREE_TWO * 2, then=_call("propose_transfer", RENT, call_id="toolu_02"))

    s.loop.handle(USER, _user(RENT_REQUEST))

    assert "first_transfer_to_payee" not in _councils(s)[-1]["council"]["triggers"]


def test_a_new_payee_on_a_corridor_already_paid_over_fires_only_the_payee_trigger():
    s = _paid_rent(THREE_TWO * 2, then=_call("propose_transfer", OTHER_PAYEE, call_id="toolu_02"))
    s.mandates[USER] = s.mandates[USER].model_copy(
        update={"allowed_payees": {"landlord_sp", "landlord_two"}}
    )

    s.loop.handle(USER, _user("Send 1,200 SGD rent to landlord_two"))

    triggers = _councils(s)[-1]["council"]["triggers"]
    assert "first_transfer_to_payee" in triggers
    assert "first_transfer_on_corridor" not in triggers


def test_a_cheapest_route_that_is_not_the_fastest_fires():
    assert "cost_and_speed_differ" in _triggers(router=SlowCheapRouter())


def test_one_route_that_is_both_cheapest_and_fastest_does_not_fire():
    assert "cost_and_speed_differ" not in _triggers()


def test_a_degraded_candidate_route_fires():
    assert "route_degraded_or_down" in _triggers(router=DegradedRouter())


def test_candidate_routes_that_are_all_up_do_not_fire():
    assert "route_degraded_or_down" not in _triggers()


def test_a_student_in_a_rescue_state_fires(monkeypatch):
    monkeypatch.setattr(AgentLoop, "_in_rescue", lambda self, user_id: True)

    assert "rescue_state" in _triggers()


def test_no_rescue_state_today_does_not_fire():
    assert "rescue_state" not in _triggers()


def test_no_trigger_means_no_council_and_no_advice_in_the_reply():
    s = _paid_rent(THREE_TWO, then=_call("propose_transfer", SMALL, call_id="toolu_02"))

    reply = s.loop.handle(USER, _user("Send 700 SGD rent to landlord_sp"))

    assert _kinds(s.ledger)[-2:] == ["proposal", "decision"]
    assert len(_councils(s)) == 1
    assert reply.confirmation is not None
    assert reply.confirmation.council is None
    assert "council" not in reply.text


def test_a_refused_transfer_never_convenes_a_council():
    s = _rent(arguments=OVER_LIMIT)

    reply = s.loop.handle(USER, _user("Send 3,000 SGD rent to landlord_sp"))

    assert reply.decision.allowed is False
    assert _kinds(s.ledger) == ["proposal", "decision"]


def test_a_read_never_convenes_a_council():
    s = _setup([_call("read_balance", {}), _say("You have 2,300 SGD.")], council=_council(THREE_TWO))

    s.loop.handle(USER, _user("How much do I have?"))

    assert "council" not in _kinds(s.ledger)


# The chair's arithmetic


def test_voices_that_all_agree_score_no_disagreement():
    s = _rent(ALL_WISE)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert _advice(s)["disagreement"] == 0.0
    assert RUNNER_UP_SENTENCE not in reply.text


def test_three_of_five_agreeing_score_the_threshold_exactly_and_hide_the_runner_up():
    s = _rent(THREE_TWO)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert _advice(s)["disagreement"] == 0.4
    assert RUNNER_UP_SENTENCE not in reply.text
    assert WIRE_REASON not in reply.text


def test_two_of_five_agreeing_score_above_the_threshold_and_show_the_runner_up():
    s = _rent(TWO_TWO_WAIT)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)
    assert advice["disagreement"] == 0.6
    assert advice["chosen"] == "wise"
    assert advice["runner_up"] == "bank_wire"
    assert reply.text == (
        f"{CONFIRM_TEXT} {COUNCIL_SENTENCE} {' '.join([WISE_REASON] * 2)} "
        f"{RUNNER_UP_SENTENCE} {' '.join([WIRE_REASON] * 2)}"
    )


def test_an_abstention_counts_in_neither_the_tally_nor_the_share():
    s = _rent(THREE_ONE_ABSTAIN)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)
    assert advice["disagreement"] == 0.25
    assert advice["chosen"] == "wise"
    assert advice["voices"][-1]["abstained"] is True
    assert advice["voices"][-1]["raw"] == ABSTAINING
    assert advice["reason"] == " ".join([WISE_REASON] * 3)
    assert RUNNER_UP_SENTENCE not in reply.text


def test_a_malformed_answer_abstains_without_raising():
    s = _rent(THREE_ONE_ABSTAIN)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert reply.confirmation is not None
    assert [voice.get("abstained", False) for voice in _advice(s)["voices"]] == [False] * 4 + [True]


def test_a_position_that_is_not_a_usable_rail_abstains():
    s = _rent(UNUSABLE_RAIL)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)
    assert advice["chosen"] == NO_ANSWER
    assert all(voice["abstained"] for voice in advice["voices"])
    assert reply.confirmation.selected_route.rail == "wise"


def test_every_voice_saying_wait_makes_the_chair_say_wait_and_still_offers_the_confirmation():
    s = _rent(ALL_WAIT)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)
    assert advice["chosen"] == WAIT
    assert advice["disagreement"] == 0.0
    assert reply.text == f"{CONFIRM_TEXT} {WAIT_SENTENCE} {' '.join([WAIT_REASON] * len(VOICES))}"
    assert reply.confirmation is not None
    assert reply.confirmation.selected_route.rail == "wise"
    assert reply.confirmation.council.chosen == WAIT


def test_no_voice_validating_gives_no_answer_and_the_loop_proceeds_as_before():
    s = _rent(NONE_VALID)

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)
    assert advice["chosen"] == NO_ANSWER
    assert advice["reason"] == ""
    assert advice["disagreement"] == 0.0
    assert reply.confirmation.selected_route.rail == "wise"
    assert reply.text == CONFIRM_TEXT


def test_the_runner_up_reason_is_read_from_the_voices_that_chose_it():
    s = _rent(TWO_TWO_WAIT)
    s.loop.handle(USER, _user(RENT_REQUEST))

    advice = _advice(s)

    assert reason_for(advice, "bank_wire") == " ".join([WIRE_REASON] * 2)
    assert reason_for(advice, WAIT) == WAIT_REASON
    assert reason_for(advice, "sim_pix") == ""


# The council never executes, never blocks, and never holds a secret


def test_the_council_holds_only_its_adapter():
    adapter = FakeModelAdapter(THREE_TWO)

    council = FiveVoiceCouncil(adapter)

    assert isinstance(council, Council)
    assert list(inspect.signature(FiveVoiceCouncil.__init__).parameters) == ["self", "adapter"]
    assert list(vars(council).values()) == [adapter]
    assert not [
        value
        for value in vars(council).values()
        if isinstance(value, (Rail, Ledger, Router, MandateEngine, AgentLoop))
    ]


def test_the_council_makes_exactly_five_calls_with_no_tools():
    adapter = FakeModelAdapter(THREE_TWO)
    s = _setup([_call("propose_transfer", RENT)], council=FiveVoiceCouncil(adapter))

    s.loop.handle(USER, _user(RENT_REQUEST))

    assert len(adapter.calls) == len(VOICES)
    assert all(tools == [] for _, tools in adapter.calls)
    assert [len(messages) for messages, _ in adapter.calls] == [2] * len(VOICES)


def test_the_council_entry_carries_no_confirmation_token():
    s = _rent()

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    token = reply.confirmation.confirmation_token
    assert token
    assert token not in json.dumps(_entry(s), default=str)
    for entry in s.ledger.entries():
        assert token not in json.dumps(entry.payload, default=str)


def test_no_voice_prompt_carries_the_token_or_the_students_own_words():
    adapter = FakeModelAdapter(THREE_TWO)
    s = _setup([_call("propose_transfer", RENT)], council=FiveVoiceCouncil(adapter))

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    token = reply.confirmation.confirmation_token
    for messages, _ in adapter.calls:
        prompt = "\n".join(message.text for message in messages)
        assert token not in prompt
        assert RENT_REQUEST not in prompt
        assert "1,200" not in prompt


def test_a_council_that_raises_leaves_a_note_and_the_payment_path_untouched():
    s = _rent([])

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert _kinds(s.ledger) == ["proposal", "decision", "note"]
    note = next(entry.payload for entry in s.ledger.entries() if entry.kind == "note")
    assert note["kind"] == "council_failed"
    assert "RuntimeError" in note["error"]
    assert reply.confirmation is not None
    assert reply.confirmation.selected_route.rail == "wise"
    assert reply.confirmation.council is None
    assert reply.text == CONFIRM_TEXT


def test_an_escalated_turn_leaves_the_model_call_cap_alone():
    adapter = FakeModelAdapter(THREE_TWO)
    s = _setup([_call("propose_transfer", RENT)], council=FiveVoiceCouncil(adapter))

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert MAX_MODEL_CALLS_PER_TURN == 8
    assert len(s.adapter.calls) == 1
    assert len(adapter.calls) == len(VOICES)
    assert adapter is not s.adapter
    assert reply.confirmation is not None


# With no council, nothing changes


def test_without_a_council_the_transfer_reply_and_trail_are_what_they_were():
    s = _setup([_call("propose_transfer", RENT)])

    reply = s.loop.handle(USER, _user(RENT_REQUEST))

    assert reply.text == CONFIRM_TEXT
    assert _kinds(s.ledger) == ["proposal", "decision"]
    assert reply.confirmation.council is None
    assert reply.confirmation.selected_route.rail == "wise"
    assert [route.rail for route in reply.confirmation.routes] == ["wise", "sim_pix", "bank_wire"]
