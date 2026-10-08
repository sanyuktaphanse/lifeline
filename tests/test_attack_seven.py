"""The Stage 10 adversarial security review.

Each test here is a break that independent attackers found and that three independent skeptics failed to
refute. It failed on main before its fix. Every step runs through the engine, the agent loop or the API, with
the scripted FakeModelAdapter acting as a compromised model, and nothing in production code is replaced.
"""

from datetime import timedelta

from fastapi.testclient import TestClient

from api.main import create_app
from contracts.schemas import Action, ActionType, Source, Tier
from core.fake_adapter import FakeModelAdapter
from core.mandate import check
from core.standing import next_occurrence
from tests.test_agent import RENT, STANDING_ARGS, STANDING_ID, USER, _call, _create_standing, _kinds, _say, _setup, _user
from tests.test_standing import DUE, PERIOD, SCHEDULE, _mandate, _run
from tests.test_standing import STANDING_ID as ENGINE_STANDING_ID

CANCEL_REQUEST = "Cancel this month's rent run, I am moving out"


def _cancel(at=None) -> Action:
    return Action(
        type=ActionType.CANCEL_STANDING_RUN,
        source=Source.USER_TURN,
        idempotency_key="student_001:t2:cancel_standing_run:1",
        requested_at=at or DUE - timedelta(hours=72),
        standing_mandate_id=ENGINE_STANDING_ID,
    )


# X17, C-B1: a standing run the student cancelled was paid from chat at T1 with no confirmation.


def test_a_run_for_a_period_the_student_cancelled_escalates_under_r13():
    decision = check(_run(source=Source.USER_TURN, idempotency_key="txn-after-cancel"), _mandate(), [_cancel()])

    assert decision.rule_ids == ["R13", "R11"]
    assert decision.tier is Tier.T2
    assert decision.requires_confirmation is True
    assert f"the student cancelled the run for {PERIOD}" in decision.reasons[0]


def test_a_scheduled_run_for_a_cancelled_period_is_not_within_pattern():
    decision = check(_run(), _mandate(), [_cancel()])

    assert "R12" not in decision.rule_ids
    assert decision.tier is Tier.T2


def test_a_cancel_after_this_period_ran_cancels_the_next_period_only():
    # The loop cancels the next period that has not run, so the engine reads a cancel the same way.
    ran = _run()
    cancel = _cancel(at=DUE + timedelta(hours=1))
    _, next_due = next_occurrence(SCHEDULE, DUE + timedelta(hours=24))
    next_run = _run(idempotency_key="txn-next-period", requested_at=next_due)

    this_period = check(_run(idempotency_key="txn-second", requested_at=DUE + timedelta(hours=2)), _mandate(), [ran, cancel])
    next_period = check(next_run, _mandate(), [ran, cancel])

    assert "cancelled" not in this_period.reasons[0]
    assert f"the student cancelled the run for {next_due.year:04d}-{next_due.month:02d}" in next_period.reasons[0]


def test_a_cancel_of_another_standing_mandate_leaves_this_run_within_pattern():
    other = _cancel().model_copy(update={"standing_mandate_id": "student_001-standing-other"})

    assert check(_run(), _mandate(), [other]).rule_ids == ["R12"]


def _cancelled_setup():
    s = _setup([])
    _create_standing(s, notice_hours=300, cancel_window_hours=24)
    s.adapter._responses[:0] = [_call("cancel_standing_run", {"standing_mandate_id": STANDING_ID}), _say("Cancelled.")]
    s.loop.handle(USER, _user(CANCEL_REQUEST))
    return s


def test_a_cancelled_standing_run_is_not_paid_from_chat_without_confirmation():
    s = _cancelled_setup()
    s.adapter._responses[:0] = [_call("propose_transfer", {**RENT, "standing_mandate_id": STANDING_ID})]

    reply = s.loop.handle(USER, _user("What is my balance?"))

    assert reply.receipt is None, reply.text
    assert "receipt" not in _kinds(s.ledger)
    assert reply.confirmation is not None
    assert reply.decision.rule_ids == ["R13", "R11"]


def test_the_student_can_still_pay_a_cancelled_period_by_confirming_it():
    s = _cancelled_setup()
    s.adapter._responses[:0] = [_call("propose_transfer", {**RENT, "standing_mandate_id": STANDING_ID})]
    token = s.loop.handle(USER, _user("Actually pay this month's rent now")).confirmation.confirmation_token

    paid = s.loop.handle(USER, _user("Yes"), confirmation_token=token)

    assert paid.receipt is not None


def test_a_cancelled_standing_run_stays_cancelled_after_a_rebuild_from_the_ledger():
    s = _cancelled_setup()
    rebuilt = _setup([_call("propose_transfer", {**RENT, "standing_mandate_id": STANDING_ID})], ledger=s.ledger)

    reply = rebuilt.loop.handle(USER, _user("What is my balance?"))

    assert reply.receipt is None, reply.text
    assert reply.decision.rule_ids == ["R13", "R11"]


def test_a_cancelled_standing_run_is_not_paid_from_chat_over_http(monkeypatch, tmp_path):
    monkeypatch.setenv("COUNCIL", "")
    adapter = FakeModelAdapter(
        [
            _call("create_standing_mandate", {**STANDING_ARGS, "notice_hours": 300, "cancel_window_hours": 24}),
            _call("cancel_standing_run", {"standing_mandate_id": STANDING_ID}),
            _say("Cancelled."),
            _call("propose_transfer", {**RENT, "standing_mandate_id": STANDING_ID}),
        ]
    )
    client = TestClient(
        create_app(
            adapter=adapter,
            ledger_path=tmp_path / "ledger.jsonl",
            conversations_path=tmp_path / "conversations.jsonl",
            tick_seconds=None,
        )
    )
    proposed = client.post("/chat", json={"user_id": USER, "text": "Pay 1,200 SGD rent to landlord_sp in Brazil every month"})
    client.post("/confirm", json={"user_id": USER, "confirmation_token": proposed.json()["confirmation"]["confirmation_token"]})
    client.post("/chat", json={"user_id": USER, "text": CANCEL_REQUEST})

    reply = client.post("/chat", json={"user_id": USER, "text": "What is my balance?"}).json()

    assert reply["receipt"] is None, reply["text"]
    assert reply["decision"]["rule_ids"] == ["R13", "R11"]
