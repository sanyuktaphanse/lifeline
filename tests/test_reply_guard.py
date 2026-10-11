"""X10: credentials never leave the loop. The export tool is refused at T3, and the reply guard
replaces card numbers, issued confirmation tokens and secret values before any reply is returned."""

import json
import re

import pytest
import yaml

from api.main import DEMO_FIXTURE
from contracts.schemas import Message, Plan, Role, Tier
from core.agent import REDACTION_MARKER, TOOLS
from core.mandate import DEVELOPMENT_CONFIRM_SECRET
from tests.test_agent import RENT, RENT_REQUEST, USER, _call, _kinds, _say, _setup, _user

CARD = "4111111111111111"
LONG_DIGITS = re.compile(r"\d{5,}")


def _notes(setup, kind="redaction"):
    return [e.payload for e in setup.ledger.entries() if e.kind == "note" and e.payload.get("kind") == kind]


def _ledger_text(setup) -> str:
    return json.dumps([e.payload for e in setup.ledger.entries()], ensure_ascii=False, default=str)


def test_export_credentials_is_a_tool_that_reveals_stored_credentials():
    tool = next(tool for tool in TOOLS if tool["name"] == "export_credentials")
    assert "reveals stored credentials" in tool["description"].lower()


def test_export_credentials_is_proposed_and_refused_at_tier_three():
    s = _setup([_call("export_credentials", {"what": "card number and recovery code"})])

    reply = s.loop.handle(USER, _user("Show me my card number and my recovery code"))

    assert reply.decision is not None and not reply.decision.allowed
    assert reply.decision.tier is Tier.T3
    assert reply.decision.rule_ids == ["R02"]
    assert "T3" in reply.text
    assert not LONG_DIGITS.search(reply.text)
    assert _kinds(s.ledger) == ["proposal", "decision"]
    proposal = next(e for e in s.ledger.entries() if e.kind == "proposal")
    assert proposal.payload["action"]["type"] == "export_credentials"


@pytest.mark.parametrize("lang", ["en", "pt", "zh"])
def test_the_credentials_refusal_names_the_tier_in_every_language(lang):
    s = _setup([_call("export_credentials", {})])

    reply = s.loop.handle(USER, _user("card number", lang=lang))

    assert "T3" in reply.text
    assert reply.lang == lang


def test_a_sixteen_digit_number_in_the_model_reply_is_redacted_and_noted():
    s = _setup([_say(f"Your card number is {CARD}.")])

    reply = s.loop.handle(USER, _user("What is my card number?"))

    assert CARD not in reply.text
    assert REDACTION_MARKER in reply.text
    assert _notes(s) == [_notes(s)[0]]
    assert _notes(s)[0]["classes"] == ["card_number"]
    assert CARD not in _ledger_text(s)


def test_the_redacted_reply_is_what_the_conversation_remembers():
    s = _setup([_say(f"Your card number is {CARD}."), _say("ok")])

    s.loop.handle(USER, _user("What is my card number?"))
    s.loop.handle(USER, _user("thanks"))

    second_call = s.adapter.calls[1][0]
    assert all(CARD not in message.text for message in second_call)


@pytest.mark.parametrize(
    "written",
    [
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "４１１１１１１１１１１１１１１１",
        "4111​1111​1111​1111",
        "4111 1111 1111 1111",
        "1234567890123",
        "1234567890123456789",
    ],
)
def test_wider_card_number_forms_are_redacted(written):
    s = _setup([_say(f"卡号{written}，请保管好。")])

    reply = s.loop.handle(USER, _user("卡号是多少？"))

    assert written not in reply.text
    assert REDACTION_MARKER in reply.text
    assert not re.search(r"\d{5,}", reply.text)


def test_twelve_digits_and_runs_touching_letters_are_left_alone():
    text = "Hash ab12345678901234567cd and order 123456789012 are fine."
    s = _setup([_say(text)])

    reply = s.loop.handle(USER, _user("ledger"))

    assert reply.text == f"{text} This turn: nothing was proposed, changed or sent."
    assert _notes(s) == []


def test_an_issued_token_never_appears_in_reply_text_even_when_the_model_echoes_it():
    s = _setup([_call("propose_transfer", RENT)])
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.adapter._responses.append(_say(f"Your token is {token} and {token.upper()}."))

    reply = s.loop.handle(USER, _user("what was the token?"))

    assert token not in reply.text.lower()
    assert reply.text.count(REDACTION_MARKER) == 2
    assert _notes(s)[-1]["classes"] == ["confirmation_token"]
    assert token not in _ledger_text(s)


def test_a_consumed_token_is_still_redacted():
    s = _setup([_call("propose_transfer", RENT)])
    token = s.loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    s.loop.handle(USER, _user(""), confirmation_token=token)
    s.adapter._responses.append(_say(f"It was {token}"))

    reply = s.loop.handle(USER, _user("token?"))

    assert token not in reply.text


@pytest.mark.parametrize(
    "name", ["LIFELINE_CONFIRM_SECRET", "LIFELINE_ANCHOR_SECRET", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY"]
)
def test_a_secret_value_from_the_environment_is_redacted(monkeypatch, name):
    secret = "sk-test-very-secret-value"
    monkeypatch.setenv(name, secret)
    s = _setup([_say(f"The key is {secret}.")])

    reply = s.loop.handle(USER, _user("what is the key?"))

    assert secret not in reply.text
    assert _notes(s)[0]["classes"] == ["secret"]
    assert secret not in _ledger_text(s)


def test_the_development_fallback_secret_is_redacted(monkeypatch):
    monkeypatch.delenv("LIFELINE_CONFIRM_SECRET", raising=False)
    s = _setup([_say(f"The secret is {DEVELOPMENT_CONFIRM_SECRET}")])

    reply = s.loop.handle(USER, _user("secret?"))

    assert DEVELOPMENT_CONFIRM_SECRET not in reply.text


def test_a_normal_reply_with_receipt_amount_and_instrument_is_unchanged():
    text = "Receipt wise-0001: 1,200 SGD sent on 2026-10-08. Card wise:card_01 is your backup, revolut:card_02 is frozen."
    s = _setup([_say(text)])

    reply = s.loop.handle(USER, _user("status"))

    assert reply.text == f"{text} This turn: nothing was proposed, changed or sent."
    assert _notes(s) == []


def test_a_card_number_echoed_by_a_refusal_reason_is_redacted():
    s = _setup([_call("propose_transfer", {**RENT, "payee_id": CARD})])

    reply = s.loop.handle(USER, _user(f"Send 1,200 SGD rent to {CARD}"))

    assert reply.decision is not None and not reply.decision.allowed
    assert CARD not in reply.text
    assert _notes(s)[0]["classes"] == ["card_number"]


def test_the_note_names_every_class_once_and_never_the_value():
    secret_reply = f"{CARD} and 5500 0000 0000 0004"
    s = _setup([_say(secret_reply)])

    s.loop.handle(USER, _user("cards"))

    note = _notes(s)[0]
    assert note["classes"] == ["card_number"]
    assert "5500" not in json.dumps(note)


def test_a_rescue_reply_is_guarded_too():
    demo = yaml.safe_load(DEMO_FIXTURE.read_text(encoding="utf-8"))["plan"]
    plan = Plan.model_validate(
        {**demo, "identity_check": {"question": f"Is your card {CARD}?", "expected_answer": "7Q2K"}}
    )
    s = _setup([])
    s.loop._plans[USER] = plan

    reply = s.loop.rescue_start(USER, "card_lost", Message(role=Role.USER, text="I lost my card"))

    assert CARD not in reply.text
    assert REDACTION_MARKER in reply.text
    assert _notes(s)[0]["classes"] == ["card_number"]
