"""The findings of the first live run. Every test here uses the fake adapter, so nothing makes a real provider call."""

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
