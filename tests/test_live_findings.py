"""The findings of the first live run. Every test here uses the fake adapter, so nothing makes a real provider call."""

from decimal import Decimal

from contracts.schemas import Message, Role, ToolCall
from core.harness import FAILED, PASSED, evaluate, render_live_report, strip_read_triples
from tests.test_live_harness import ANSWERS, GENERATED, SCRIPTED, _live, _propose, _provider, _say, _suites


def _read(number: int = 1) -> Message:
    call = ToolCall(id=f"toolu_read_{number}", name="read_balance", arguments={})
    return Message(role=Role.ASSISTANT, text="", tool_calls=[call], provider="anthropic", model="live-model")


def _triple(key: str, tier: str = "T0", allowed: bool = True) -> list[tuple[str, dict]]:
    action = {"type": "read_balance", "idempotency_key": key}
    return [
        ("proposal", {"action": action}),
        ("decision", {"idempotency_key": key, "decision": {"allowed": allowed, "tier": tier}}),
        ("execution", {"action": action}),
    ]


# One. Live mode accepts read only tool trails.


def test_a_t0_triple_is_stripped_and_counted():
    entries = [*_triple("k1"), ("proposal", {"action": {"idempotency_key": "k2"}}), ("decision", {"idempotency_key": "k2", "decision": {"allowed": True, "tier": "T2"}}), *_triple("k3")]

    kinds, stripped = strip_read_triples(entries)

    assert kinds == ["proposal", "decision"]
    assert stripped == 2


def test_only_a_whole_allowed_t0_triple_with_one_key_is_stripped():
    t1 = _triple("k1", tier="T1")
    refused = _triple("k2", allowed=False)[:2]
    mixed = [*_triple("k3")[:2], ("execution", {"action": {"idempotency_key": "other"}})]
    noted = [*_triple("k4")[:2], ("note", {}), _triple("k4")[2]]

    for entries in (t1, refused, mixed, noted):
        kinds, stripped = strip_read_triples(entries)
        assert kinds == [kind for kind, _ in entries]
        assert stripped == 0


def test_live_mode_passes_a_run_whose_model_reads_before_it_acts_and_reports_how_many_reads_it_stripped(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)
    provider = _provider(*ANSWERS, _read(1), _read(2), _propose())

    [entry] = _live(suites, provider)
    report = render_live_report([entry], provider, "abc123", GENERATED, 1.0, None)

    assert entry.runs[0].failures == []
    assert entry.runs[0].stripped == 2
    assert "| T06 | tasks | Entry T06 | en | passed | 1 | 2 |" in report


def test_the_scripted_mode_stays_exact_about_reads(tmp_path):
    scenario = {**SCRIPTED, "runs": [{**SCRIPTED["runs"][0], "turns": [
        SCRIPTED["runs"][0]["turns"][0],
        {**SCRIPTED["runs"][0]["turns"][1], "model": [{"calls": [{"name": "read_balance", "arguments": {}}]}, *SCRIPTED["runs"][0]["turns"][1]["model"]]},
    ]}]}
    suites = _suites(tmp_path, scenario)

    [entry] = evaluate(suites, suites / "scenarios")

    assert entry.status == FAILED
    assert any(failure.startswith("ledger kinds were ['proposal', 'decision', 'execution', 'proposal', 'decision']") for failure in entry.runs[0].failures)


def test_the_money_moving_kinds_must_still_appear_in_live_mode(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)

    [entry] = _live(suites, _provider(*ANSWERS, _read(1), _say("You have enough for the rent.")))

    assert entry.status == FAILED
    assert "ledger kinds were [], expected ['proposal', 'decision']" in entry.runs[0].failures
    assert entry.runs[0].stripped == 1


def test_a_read_the_scenario_expects_is_stripped_from_the_expectation_as_well(tmp_path):
    # The scripted run reads once and the expectation lists that read; a live model that reads twice or not at all
    # leaves the same trail once reads are set aside on both sides.
    scenario = {
        "id": "T01",
        "live": True,
        "runs": [{"lang": "en", "turns": [{"user": "What is my balance?", "model": [{"calls": [{"name": "read_balance", "arguments": {}}]}, {"text": "Here it is."}]}],
                  "expected": {"reply": "answer", "ledger": ["proposal", "decision", "execution"]}}],
    }
    suites = _suites(tmp_path, scenario)

    [twice] = _live(suites, _provider(_read(1), _read(2), _say("You have 2300 SGD.")))
    [never] = _live(suites, _provider(_say("You have 2300 SGD.")))

    assert (twice.status, twice.runs[0].stripped) == (PASSED, 2)
    assert (never.status, never.runs[0].stripped) == (PASSED, 0)


# Two. The model is told what the engine will decide on.

FIVE_RULES = (
    "Propose every payment the student asks for through propose_transfer, and never refuse it or judge a limit "
    "in your own words, because the engine decides and explains with a rule id.",
    "Read the balance again with read_balance whenever the student asks for it, and never answer it from memory.",
    "Never recommend a simulated route for real money, and say that a route is simulated whenever it is.",
    "Never say you can change a limit or a setting; call the tool, such as change_limit, and let the code answer.",
    "Call add_payee only when the student asks to add a payee.",
)


def _system_prompt(setup, call: int = 0) -> str:
    [system] = [message for message in setup.adapter.calls[call][0] if message.role is Role.SYSTEM]
    return system.text


def test_the_mandate_block_lists_the_codes_limits_and_balances_exactly_as_the_mandate_holds_them():
    from core.agent import mandate_block
    from tests.test_agent import _mandate

    mandate = _mandate().model_copy(update={
        "allowed_payees": {"self_sg", "landlord_sp"},
        "allowed_corridors": {"SG>SG", "SG>BR"},
        "allowed_purposes": {"rent", "emergency"},
    })

    block = mandate_block(mandate, {"SGD": Decimal("2300"), "BRL": Decimal("150.50")})

    assert block == (
        "What the mandate engine decides on, from the student's current mandate:\n"
        "Allowed payee ids: landlord_sp, self_sg.\n"
        "Allowed corridor codes: SG>BR, SG>SG.\n"
        "Allowed purpose codes: emergency, rent.\n"
        "Per transaction limit: 1500 SGD. Daily limit: 2500 SGD.\n"
        "Balances: 150.50 BRL, 2300 SGD.\n"
        "Pass these codes to tools exactly as written here and never translate them."
    )


def test_a_mandate_with_nothing_allowed_says_none_rather_than_leaving_a_gap():
    from core.agent import mandate_block
    from tests.test_agent import _mandate

    block = mandate_block(_mandate().model_copy(update={"allowed_payees": set()}), {})

    assert "Allowed payee ids: none.\n" in block
    assert "Balances: none on file.\n" in block


# The sixth rule came with the turn summary. Source: docs/decisions.md, decision 146.
SIXTH_RULE = "Never say a payment was sent, done or submitted; the code says that from the ledger."


def test_every_turn_sends_the_block_and_the_six_rules_in_the_system_prompt_in_every_language():
    from core.agent import PROMPT_RULES, mandate_block
    from tests.test_agent import USER, _say as say, _setup, _user

    setup = _setup([say("Hi."), say("Oi."), say("你好。")])
    for lang in ("en", "pt", "zh"):
        setup.loop.handle(USER, _user("Hello", lang=lang))

    assert PROMPT_RULES == (*FIVE_RULES, SIXTH_RULE)
    for call in range(3):
        prompt = _system_prompt(setup, call)
        assert mandate_block(setup.mandates[USER], {"SGD": Decimal("2300"), "BRL": Decimal("150")}) in prompt
        assert "Allowed purpose codes: rent." in prompt
        for rule in PROMPT_RULES:
            assert rule in prompt


def test_the_block_follows_the_current_mandate_after_a_payee_is_added():
    from tests.test_agent import USER, _call, _say as say, _setup, _user

    setup = _setup([_call("add_payee", {"payee_id": "ana_rio", "display_name": "Ana"}), say("Hello.")])
    proposed = setup.loop.handle(USER, _user("Add Ana as a payee, id ana_rio"))
    setup.loop.handle(USER, _user("Yes"), confirmation_token=proposed.confirmation.confirmation_token)
    setup.loop.handle(USER, _user("Thanks"))

    assert "Allowed payee ids: landlord_sp.\n" in _system_prompt(setup, 0)
    assert "Allowed payee ids: ana_rio, landlord_sp.\n" in _system_prompt(setup, 1)


# Three. Balances go down.


def _balances_line(setup, call: int = -1) -> str:
    return next(line for line in _system_prompt(setup, call).splitlines() if line.startswith("Balances: "))


def _paid_rent(responses, **setup_fields):
    """A setup that has proposed and confirmed the 1,200 SGD rent, with the given model answers after it."""
    from tests.test_agent import RENT as AGENT_RENT, USER, _call, _setup, _user

    setup = _setup([_call("propose_transfer", AGENT_RENT), *responses], **setup_fields)
    token = setup.loop.handle(USER, _user("Send 1,200 SGD rent to landlord_sp in Brazil")).confirmation.confirmation_token
    paid = setup.loop.handle(USER, _user("Yes"), confirmation_token=token)
    return setup, paid


def test_a_completed_payment_lowers_the_balance_by_the_amount_and_the_fee():
    from tests.test_agent import USER, _call, _say as say, _user

    setup, paid = _paid_rent([_call("read_balance", {}), say("You have 1094.40 SGD.")])
    setup.loop.handle(USER, _user("What is my balance?"))

    assert paid.receipt.rail == "wise"
    assert _balances_line(setup, 1) == "Balances: 150 BRL, 1094.40 SGD."
    tool_results = [message.text for message in setup.adapter.calls[-1][0] if message.role is Role.TOOL]
    assert '"SGD": "1094.40"' in tool_results[-1]


def test_a_receipt_issued_as_failed_moves_nothing():
    from contracts.schemas import ReceiptStatus
    from rails.fake_rail import FakeRail
    from tests.test_agent import USER, _say as say, _user

    rails = {"wise": FakeRail(name="wise", simulated=False, issue_status=ReceiptStatus.FAILED)}
    setup, paid = _paid_rent([say("Noted.")], rails=rails)
    setup.loop.handle(USER, _user("Thanks"))

    assert paid.receipt.status is ReceiptStatus.FAILED
    assert _balances_line(setup) == "Balances: 150 BRL, 2300 SGD."


def test_a_cancelled_and_returned_payment_gives_the_amount_and_the_fee_back_once():
    from contracts.schemas import ReceiptStatus
    from rails.fake_rail import FakeRail
    from tests.test_agent import USER, _call, _say as say, _user

    rails = {"wise": FakeRail(name="wise", simulated=False, issue_status=ReceiptStatus.CREATED)}
    setup, paid = _paid_rent(
        [_call("cancel_transfer", {"receipt_id": "wise-0001"}), _call("trace_transfer", {"receipt_id": "wise-0001"}), say("It was returned."), say("Ok.")],
        rails=rails,
    )
    cancel = setup.loop.handle(USER, _user("Cancel wise-0001"))
    setup.loop.handle(USER, _user("Yes"), confirmation_token=cancel.confirmation.confirmation_token)
    setup.loop.handle(USER, _user("Where is wise-0001?"))
    setup.loop.handle(USER, _user("Thanks"))

    assert paid.receipt.status is ReceiptStatus.CREATED
    assert _balances_line(setup, 1) == "Balances: 150 BRL, 1094.40 SGD."
    # 1094.40 plus 1200 and 5.60 back is 2300.00; Decimal keeps the places of the fee.
    assert _balances_line(setup) == "Balances: 150 BRL, 2300.00 SGD."


def test_a_trace_that_finds_the_payment_returned_gives_it_back_once():
    from rails.fake_rail import FakeRail, scripted_traces
    from tests.test_agent import USER, _call, _say as say, _user

    traces = scripted_traces({"wise": [{"receipt_id": "wise-0001", "status": "returned", "typical_duration_source": "fixture", "next_steps": [], "warnings": []}]})
    rails = {"wise": FakeRail(traces["wise"], name="wise", simulated=False)}
    trace = _call("trace_transfer", {"receipt_id": "wise-0001"})
    setup, _ = _paid_rent([trace, say("Returned."), trace, say("Still returned."), say("Ok.")], rails=rails)
    setup.loop.handle(USER, _user("Where is wise-0001?"))
    setup.loop.handle(USER, _user("And now?"))
    setup.loop.handle(USER, _user("Thanks"))

    # The prompt is built when a turn starts: before the first trace, after it, and after the second.
    assert _balances_line(setup, 1) == "Balances: 150 BRL, 1094.40 SGD."
    assert _balances_line(setup, 3) == "Balances: 150 BRL, 2300.00 SGD."
    assert _balances_line(setup) == "Balances: 150 BRL, 2300.00 SGD."


def test_the_balances_rebuild_from_the_ledger_on_restart():
    from tests.test_agent import USER, _say as say, _setup, _user

    first, _ = _paid_rent([])
    restarted = _setup([say("Hello again.")], ledger=first.ledger)
    restarted.loop.handle(USER, _user("Hello"))

    assert _balances_line(restarted) == "Balances: 150 BRL, 1094.40 SGD."


# Four. The Anthropic default.


def test_the_env_example_names_the_anthropic_default_in_a_comment_and_leaves_the_value_empty():
    from pathlib import Path

    from core.model_adapter import DEFAULT_ANTHROPIC_MODEL

    lines = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8").splitlines()
    index = lines.index("ANTHROPIC_MODEL=")

    assert DEFAULT_ANTHROPIC_MODEL == "claude-opus-5"
    assert lines[index - 1] == "# ANTHROPIC_MODEL defaults to claude-opus-5 on purpose; leave it empty to use that default."
    assert all(line.startswith("#") or "=" in line for line in lines)


# A hung call fails its run instead of waiting.


def test_a_live_call_that_does_not_answer_in_time_fails_the_run_and_the_next_run_goes_on(tmp_path):
    import threading
    import time

    from core.fake_adapter import FakeModelAdapter
    from core.harness import LIVE_CALL_TIMEOUT_SECONDS, LiveProvider
    from tests.test_live_harness import _live as live

    release = threading.Event()

    class Hung(FakeModelAdapter):
        def complete(self, messages, tools):
            release.wait(5)
            return super().complete(messages, tools)

    second = {**SCRIPTED, "id": "T07"}
    suites = _suites(tmp_path, SCRIPTED, second)
    built = []

    def build(env):
        built.append(env)
        return Hung([]) if len(built) == 1 else FakeModelAdapter([*ANSWERS, _propose()])

    provider = LiveProvider("anthropic", {"MODEL_PROVIDER": "anthropic"}, build=build, call_timeout=0.2)
    started = time.monotonic()
    hung, fine = live(suites, provider)
    release.set()

    assert LIVE_CALL_TIMEOUT_SECONDS == 60
    assert time.monotonic() - started < 3
    assert hung.runs[0].failures == ["error: ModelCallTimeout, anthropic gave no answer within 0.2 seconds"]
    assert fine.status == PASSED
    assert provider.loop_calls == 3
    assert provider.answered_by == {"anthropic": 2}
