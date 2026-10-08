"""Attack four on T18, the parent as a user. Each test here fails on 4957ac1 for the reason its name gives."""

from contracts.schemas import Message, Role
from core.agent import AgentLoop
from core.fake_adapter import FakeModelAdapter
from core.harness import _who
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.monthly import month_of, summarize
from rails.fake_router import FakeRouter
from rails.sim.rules import UPI_CAP_ENTRY
from rails.sim.upi_paynow import UpiPayNowSimRail
from tests.test_agent import _call

SEND = {"amount": "40000", "currency": "INR", "corridor": "IN>SG", "payee_id": "student_001", "purpose": "gift"}


def test_a_transfer_the_rail_refused_at_the_cap_appears_in_the_monthly_note():
    who = _who({"user": {"fixture": "demo_parent"}})
    ledger = HashChainLedger()
    loop = AgentLoop(
        adapter=FakeModelAdapter([_call("propose_transfer", SEND), _call("propose_transfer", {**SEND, "amount": "30000"})]),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails={"upi_paynow_sim": UpiPayNowSimRail()},
        mandates={who.user_id: who.mandate},
        balances={who.user_id: who.balances},
        pending={},
        plans={who.user_id: who.plan},
    )
    for amount in ("40000", "30000"):
        token = loop.handle(who.user_id, Message(role=Role.USER, text=f"Send {amount} rupees to student_001 as a gift")).confirmation.confirmation_token
        reply = loop.handle(who.user_id, Message(role=Role.USER, text="Yes"), confirmation_token=token)
    assert reply.receipt is None and UPI_CAP_ENTRY in reply.text

    summary = summarize(ledger.entries(), who.user_id, month_of(ledger.entries()[-1].ts))

    # The parent confirmed 30,000 rupees and the rail refused it at the cap. The note must say so,
    # as a failure or as a refusal; today it lists neither, so the month reads as if nothing went wrong.
    assert summary["problems"] or summary["refusals"]["count"], summary


def test_a_rail_failure_followed_by_a_payment_on_another_route_is_not_listed():
    from tests.test_agent import RENT, RENT_REQUEST, USER, _honest_rails, _setup, _user
    from rails.fake_rail import FakeRail

    rails = {**_honest_rails(), "wise": FakeRail(name="wise", simulated=False, fail_once_keys=[f"{USER}:t1:propose_transfer:1"])}
    s = _setup([_call("propose_transfer", RENT)], rails=rails)
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)
    s.loop.handle(USER, _user("Yes"), confirmation_token=token)

    summary = summarize(s.ledger.entries(), USER, month_of(s.ledger.entries()[-1].ts))

    assert summary["problems"] == []
    assert summary["transfers"][0]["count"] == 1


def test_the_note_names_the_rail_that_refused():
    from core.monthly import render

    who = _who({"user": {"fixture": "demo_parent"}})
    ledger = HashChainLedger()
    loop = AgentLoop(
        adapter=FakeModelAdapter([_call("propose_transfer", SEND), _call("propose_transfer", {**SEND, "amount": "30000"})]),
        engine=DeterministicMandateEngine(), ledger=ledger, router=FakeRouter(),
        rails={"upi_paynow_sim": UpiPayNowSimRail()}, mandates={who.user_id: who.mandate},
        balances={who.user_id: who.balances}, pending={}, plans={who.user_id: who.plan},
    )
    for amount in ("40000", "30000"):
        token = loop.handle(who.user_id, Message(role=Role.USER, text=f"Send {amount} rupees to student_001 as a gift")).confirmation.confirmation_token
        loop.handle(who.user_id, Message(role=Role.USER, text="Yes"), confirmation_token=token)

    text = render(summarize(ledger.entries(), who.user_id, month_of(ledger.entries()[-1].ts)), "en")

    assert "upi_paynow_sim refused" in text
    assert "1 sent on IN>SG, total 40000 INR" in text
