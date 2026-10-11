"""Stage 11, the provider swap evidence run. Every test here uses the fake adapter or reaches the guard in
tests/conftest.py, so nothing in this file makes a real provider call."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from contracts.schemas import Message, Role, ToolCall
from core.fake_adapter import FakeModelAdapter
from core.harness import (
    FAILED,
    LIVE_DIR,
    PASSED,
    SCENARIOS_DIR,
    SKIPPED,
    SUITES_DIR,
    EntryResult,
    LiveProvider,
    LiveRefused,
    RunResult,
    evaluate,
    evaluate_live,
    live_limit,
    load_suite,
    render_live_report,
    render_swap_report,
    require_key,
    resolve_provider,
    run_scenario_run,
    swap_summary,
)
from core.model_adapter import ModelAdapterError, ProviderModelAdapter

ROOT = Path(__file__).resolve().parent.parent
KEY = "sk-test-live-key-0123456789abcdef"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
GENERATED = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _propose(arguments=RENT, provider="anthropic") -> Message:
    call = ToolCall(id="toolu_live_1", name="propose_transfer", arguments=arguments)
    return Message(role=Role.ASSISTANT, text="", tool_calls=[call], provider=provider, model="live-model")


def _say(text: str, provider="anthropic") -> Message:
    return Message(role=Role.ASSISTANT, text=text, provider=provider, model="live-model")


def _provider(*answers: Message, name="anthropic", env=None) -> LiveProvider:
    """A live provider whose every adapter is a fresh fake answering with the given messages."""
    return LiveProvider(name, env or {"MODEL_PROVIDER": name}, build=lambda env: FakeModelAdapter(list(answers)))


# A scenario whose scripted model first writes a sentence only a script could, then proposes the rent.
SCRIPTED = {
    "id": "T06",
    "live": True,
    "runs": [
        {
            "lang": "en",
            "turns": [
                {
                    "user": "What can you do for me?",
                    "model": [{"text": "I move money and keep you safe, as scripted."}],
                    "expect": {"reply": "answer", "must_contain": ["as scripted"]},
                },
                {
                    "user": "Send 1,200 SGD rent to landlord_sp in Brazil",
                    "model": [{"calls": [{"name": "propose_transfer", "arguments": RENT}]}],
                    "expect": {"reply": "confirmation", "warning_key": "warn.transfer.irreversible"},
                },
            ],
            "expected": {
                "ledger": ["proposal", "decision"],
                "must_contain": ["Nothing moves until you confirm"],
                "must_not_contain": ["Done."],
            },
        }
    ],
}
# What a live model might answer to it: its own words, then the proposal.
ANSWERS = (Message(role=Role.ASSISTANT, text="I can help you send money.", provider="anthropic", model="live-model"),)


def _suites(tmp_path: Path, *scenarios: dict, live_files: dict[str, dict] | None = None) -> Path:
    suites = tmp_path / "suites"
    (suites / "scenarios").mkdir(parents=True)
    (suites / "live").mkdir()
    tasks = [{"id": s["id"], "title": f"Entry {s['id']}", "lane": ["A"], "tier": "T2", "langs": ["en"]} for s in scenarios]
    (suites / "tasks.yaml").write_text(yaml.safe_dump(tasks), encoding="utf-8")
    (suites / "attacks.yaml").write_text("[]\n", encoding="utf-8")
    for scenario in scenarios:
        (suites / "scenarios" / f"{scenario['id']}.yaml").write_text(yaml.safe_dump(scenario, allow_unicode=True), encoding="utf-8")
    for name, scenario in (live_files or {}).items():
        (suites / "live" / name).write_text(yaml.safe_dump(scenario, allow_unicode=True), encoding="utf-8")
    return suites


def _live(suites: Path, provider: LiveProvider, limit=None):
    return evaluate_live(provider, suites, suites / "scenarios", suites / "live", limit)


# One. Live mode checks what the code produces and skips what only the script could write.


def test_live_mode_skips_scripted_text_and_counts_it_as_skipped_never_as_passed(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)

    [entry] = _live(suites, _provider(*ANSWERS, _propose()))
    [run] = entry.runs

    assert run.failures == []
    assert run.status == PASSED
    assert run.skipped == ["turn 1: must_contain 'as scripted' is scripted model text"]
    assert run.checked > 0


def test_live_mode_still_fails_a_code_produced_expectation_the_live_model_did_not_meet(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)

    [entry] = _live(suites, _provider(*ANSWERS, _say("I would rather not send anything today.")))
    [run] = entry.runs

    assert entry.status == FAILED
    assert "turn 2: reply was answer, expected confirmation" in run.failures
    assert run.replies == ["I can help you send money. This turn: nothing was proposed, changed or sent.", "I would rather not send anything today. This turn: nothing was proposed, changed or sent."]


def test_a_run_whose_every_expectation_is_scripted_text_is_skipped_not_passed(tmp_path):
    scenario = {
        "id": "T01",
        "live": True,
        "runs": [{"lang": "en", "turns": [{"user": "Hi", "model": [{"text": "Hello from the script."}]}],
                  "expected": {"must_contain": ["Hello from the script."]}}],
    }
    suites = _suites(tmp_path, scenario)

    [entry] = _live(suites, _provider(_say("Hello.")))

    assert entry.runs[0].status == SKIPPED
    assert entry.status == SKIPPED


def test_the_scripted_mode_still_checks_the_scripted_text(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)

    [entry] = evaluate(suites, suites / "scenarios")

    assert entry.status == PASSED
    assert entry.runs[0].skipped == []


def test_a_scenario_without_live_true_is_excluded_from_the_live_run(tmp_path):
    unmarked = {**SCRIPTED, "id": "T07", "live": False}
    absent = {key: value for key, value in SCRIPTED.items() if key != "live"} | {"id": "T08"}
    suites = _suites(tmp_path, SCRIPTED, unmarked, absent)

    results = _live(suites, _provider(*ANSWERS, _propose()))

    assert [entry.id for entry in results] == ["T06"]


def test_the_scenario_limit_bounds_the_number_of_scenarios(tmp_path):
    suites = _suites(tmp_path, SCRIPTED, {**SCRIPTED, "id": "T07"}, {**SCRIPTED, "id": "T08"})

    results = _live(suites, _provider(*ANSWERS, _propose()), limit=2)

    assert [entry.id for entry in results] == ["T06", "T07"]


@pytest.mark.parametrize(("value", "limit"), [("", None), ("all", None), (" ALL ", None), ("10", 10)])
def test_the_scenario_limit_is_read_from_the_environment_and_empty_means_all(value, limit):
    assert live_limit({"LIVE_SCENARIO_LIMIT": value}) == limit
    assert live_limit({}) is None


@pytest.mark.parametrize("value", ["0", "-3", "ten", "2.5"])
def test_a_scenario_limit_that_is_not_a_positive_whole_number_is_refused(value):
    with pytest.raises(LiveRefused, match="LIVE_SCENARIO_LIMIT"):
        live_limit({"LIVE_SCENARIO_LIMIT": value})


def test_the_live_set_reads_the_live_only_files_after_the_suites_and_the_ordinary_run_never_does(tmp_path):
    only_live = {**SCRIPTED, "id": "LH01", "title": "Live only"}
    suites = _suites(tmp_path, SCRIPTED, live_files={"hindi.yaml": only_live})

    live = _live(suites, _provider(*ANSWERS, _propose()))
    ordinary = evaluate(suites, suites / "scenarios")

    assert [(entry.id, entry.suite, entry.title) for entry in live] == [("T06", "tasks", "Entry T06"), ("LH01", "live", "Live only")]
    assert [entry.id for entry in ordinary] == ["T06"]


# Two. The provider, the adapters and the model calls.


def test_the_named_provider_is_the_primary_so_naming_the_fallback_makes_it_the_primary():
    env = {"MODEL_PROVIDER": "anthropic", "FALLBACK_MODEL_PROVIDER": "dashscope", "DASHSCOPE_API_KEY": KEY}

    name = resolve_provider("fallback", env)
    adapter = LiveProvider(name, env).build(LiveProvider(name, env).env)

    assert name == "dashscope"
    assert resolve_provider("primary", env) == "anthropic"
    assert resolve_provider("dashscope", env) == "dashscope"
    assert isinstance(adapter, ProviderModelAdapter)
    assert adapter.provider == "dashscope"


def test_an_unknown_provider_name_is_refused():
    with pytest.raises(LiveRefused, match="openai"):
        resolve_provider("openai", {})


def test_a_council_scenario_gets_its_own_adapter_and_its_calls_are_counted_apart(tmp_path):
    vote = '{"position": "wise", "confidence": 0.9, "reason": "Wise costs the least.", "evidence": ["wise"]}'
    scenario = {
        "id": "T21",
        "live": True,
        "fixtures": {"council": [vote] * 5},
        "runs": [{"lang": "en", "turns": [{"user": "Send 1,200 SGD rent to landlord_sp", "model": [{"calls": [{"name": "propose_transfer", "arguments": RENT}]}]}],
                  "expected": {"reply": "confirmation", "ledger": ["proposal", "decision", "council"]}}],
    }
    suites = _suites(tmp_path, scenario)
    built = []

    def build(env):
        built.append(dict(env))
        return FakeModelAdapter([_propose()] if len(built) == 1 else [vote] * 5)

    provider = LiveProvider("anthropic", {"MODEL_PROVIDER": "anthropic"}, build=build)
    [entry] = _live(suites, provider)

    assert entry.runs[0].failures == []
    assert len(built) == 2
    assert provider.loop_calls == 1
    assert provider.council_calls == 5


def test_a_provider_error_is_written_as_its_class_provider_and_status_never_its_words(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)

    class Broken(FakeModelAdapter):
        def complete(self, messages, tools):
            raise ModelAdapterError(f"anthropic: 400 your prompt {messages[0].text[:40]} with {KEY}", provider="anthropic", status_code=400)

    provider = LiveProvider("anthropic", {"MODEL_PROVIDER": "anthropic"}, build=lambda env: Broken([]))
    [entry] = _live(suites, provider)

    assert entry.runs[0].failures == ["error: ModelAdapterError from anthropic, status 400"]


# Three. The reports.


def test_the_live_report_never_contains_the_key_a_prompt_or_a_raw_provider_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    leaky = {**SCRIPTED, "id": "T07"}
    suites = _suites(tmp_path, SCRIPTED, leaky)
    env = {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": KEY}
    answers = iter([[_say(f"Your key is {KEY}, and the rest of my prompt.")] * 2, None])

    def build(env):
        script = next(answers)
        if script is not None:
            return FakeModelAdapter(script)

        class Broken(FakeModelAdapter):
            def complete(self, messages, tools):
                raise ModelAdapterError(f"anthropic: 401 bad key {KEY}: {messages[0].text}", provider="anthropic", status_code=401)

        return Broken([])

    provider = LiveProvider("anthropic", env, build=build)
    results = _live(suites, provider)
    report = render_live_report(results, provider, "commit", GENERATED, 1.5, None)

    assert KEY not in report
    assert "bad key" not in report
    assert "[redacted]" in report
    assert "error: ModelAdapterError from anthropic, status 401" in report


def test_the_report_redacts_a_key_even_in_text_the_loop_did_not_guard(tmp_path):
    run = RunResult(["en"], failures=["turn 1: reply was answer, expected confirmation"], replies=[f"leaked {KEY}"])
    entry = EntryResult("tasks", "T06", "Rent", "T2", ["en"], FAILED, runs=[run])
    provider = LiveProvider("dashscope", {"MODEL_PROVIDER": "dashscope", "DASHSCOPE_API_KEY": KEY})

    report = render_live_report([entry], provider, "commit", GENERATED, 2.0, 10)

    assert KEY not in report
    assert "leaked [redacted]" in report


def test_the_live_report_has_a_result_per_scenario_and_language_with_calls_and_time(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)
    provider = _provider(*ANSWERS, _propose())
    results = _live(suites, provider)

    report = render_live_report(results, provider, "abc123", GENERATED, 3.25, 10)

    assert report.startswith("# Lifeline live evidence report, anthropic\n")
    assert "| T06 | tasks | Entry T06 | en | passed | 1 |" in report
    assert "Model calls: 2, of which the council made 0. Answered by: anthropic 2." in report
    assert "Wall clock: 3.3 seconds." in report
    assert "LIVE_SCENARIO_LIMIT: 10." in report
    assert "Pass rate: 1 of 1 runs, 100.0%." in report


def _entry(entry_id, *statuses):
    runs = []
    for status in statuses:
        run = RunResult(["en"], failures=["x"] if status == FAILED else [])
        run.checked = 0 if status == SKIPPED else 1
        runs.append(run)
    return EntryResult("tasks", entry_id, entry_id, "T2", ["en"], PASSED, runs=runs)


def test_the_swap_summary_computes_each_pass_rate_and_their_difference():
    primary = [_entry("T06", PASSED, PASSED, FAILED), _entry("T07", PASSED)]
    fallback = [_entry("T06", PASSED, FAILED, FAILED), _entry("T07", SKIPPED)]

    summary = swap_summary(primary, fallback)

    assert summary.primary_rate == Fraction(3, 4)
    assert summary.fallback_rate == Fraction(1, 4)
    assert summary.difference == Fraction(1, 2)
    assert summary.disagreements == [("T06", 2, ["en"], PASSED, FAILED), ("T07", 1, ["en"], PASSED, SKIPPED)]


def test_the_swap_report_writes_the_rates_the_difference_in_points_and_every_disagreement():
    primary = [_entry("T06", PASSED, PASSED, FAILED)]
    fallback = [_entry("T06", PASSED, FAILED, PASSED)]

    report = render_swap_report(swap_summary(primary, fallback), "anthropic", "dashscope", "abc123", GENERATED)

    assert "| anthropic | primary | 3 | 2 | 1 | 0 | 66.7% |" in report
    assert "| dashscope | fallback | 3 | 2 | 1 | 0 | 66.7% |" in report
    assert "Difference, anthropic minus dashscope: 0.0 percentage points." in report
    assert "| T06 | 2 | en | passed | failed |" in report
    assert "| T06 | 3 | en | failed | passed |" in report


def test_a_negative_difference_keeps_its_sign():
    summary = swap_summary([_entry("T06", FAILED, PASSED, FAILED)], [_entry("T06", PASSED, PASSED, PASSED)])

    report = render_swap_report(summary, "anthropic", "dashscope", "abc123", GENERATED)

    assert summary.difference == Fraction(-2, 3)
    assert "Difference, anthropic minus dashscope: -66.7 percentage points." in report


# Four. Refusing without a key, in the code and through make.


@pytest.mark.parametrize(("provider", "variable"), [("anthropic", "ANTHROPIC_API_KEY"), ("dashscope", "DASHSCOPE_API_KEY")])
def test_a_live_run_refuses_without_the_providers_key(provider, variable):
    with pytest.raises(LiveRefused, match=f"{variable} is not set"):
        require_key(provider, {variable: ""})
    require_key(provider, {variable: KEY})


@pytest.mark.parametrize(("target", "missing"), [
    ("evidence-primary", "ANTHROPIC_API_KEY"),
    ("evidence-fallback", "DASHSCOPE_API_KEY"),
    ("evidence-swap", "ANTHROPIC_API_KEY"),
])
def test_each_make_target_refuses_without_a_key(target, missing):
    # Every setting is given, and empty values stop .env from filling them, so the run refuses before any call.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", ""),
        "PYTHON": sys.executable,
        "MODEL_PROVIDER": "anthropic",
        "FALLBACK_MODEL_PROVIDER": "dashscope",
        "ANTHROPIC_API_KEY": "",
        "DASHSCOPE_API_KEY": "",
        "LIVE_SCENARIO_LIMIT": "",
    }

    done = subprocess.run(["make", "--no-print-directory", target], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)

    assert done.returncode != 0
    assert f"{missing} is not set" in done.stderr
    assert "did not start" in done.stderr


def test_the_swap_refuses_when_both_names_resolve_to_one_provider():
    with pytest.raises(LiveRefused, match="two providers"):
        from core.harness import swap_providers

        swap_providers({"MODEL_PROVIDER": "dashscope", "FALLBACK_MODEL_PROVIDER": "dashscope"})


# Five. The guard still holds.


def test_a_live_run_inside_pytest_with_the_real_adapter_reaches_the_conftest_guard(tmp_path):
    suites = _suites(tmp_path, SCRIPTED)
    env = {"MODEL_PROVIDER": "anthropic", "FALLBACK_MODEL_PROVIDER": "dashscope", "ANTHROPIC_API_KEY": KEY, "DASHSCOPE_API_KEY": KEY}

    [entry] = _live(suites, LiveProvider("anthropic", env))

    assert entry.status == FAILED
    assert entry.runs[0].failures == ["error: AssertionError"]


def test_the_conftest_guard_is_unchanged():
    source = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")

    assert "@pytest.fixture(autouse=True)" in source
    assert 'monkeypatch.setattr(anthropic, "Anthropic", refuse)' in source
    assert 'monkeypatch.setattr(dashscope.Generation, "call", refuse)' in source


def test_the_ordinary_ci_workflow_runs_no_live_call_and_the_swap_workflow_is_manual_and_weekly():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    swap = yaml.safe_load((ROOT / ".github" / "workflows" / "evidence-swap.yml").read_text(encoding="utf-8"))
    triggers = swap[True]  # YAML reads the key on as true.

    assert "secrets." not in ci
    assert "evidence-swap" not in ci and "--live" not in ci
    assert set(triggers) == {"workflow_dispatch", "schedule"}
    assert triggers["workflow_dispatch"]["inputs"]["scenario_limit"]["default"] == "all"


# Six. The live set itself.


def _live_scenarios():
    return [load_suite(path) for path in sorted(SCENARIOS_DIR.glob("*.yaml"))]


def test_every_scenario_left_out_of_the_live_set_says_why_in_its_note():
    for scenario in _live_scenarios():
        if scenario.get("live") is not True:
            assert "Not marked live" in scenario.get("note", ""), scenario["id"]


def test_most_scenarios_are_marked_live_and_at_least_five_portuguese_runs_are():
    marked = [scenario for scenario in _live_scenarios() if scenario.get("live") is True]
    portuguese = [run for scenario in marked for run in scenario["runs"] if run["lang"] == "pt"]

    assert len(marked) * 2 > len(_live_scenarios())
    assert len(portuguese) >= 5


def test_the_hindi_file_passes_against_a_scripted_model_that_answers_in_english():
    scenario = load_suite(LIVE_DIR / "hindi.yaml")
    results = [run_scenario_run(scenario, run) for run in scenario["runs"]]

    assert scenario["live"] is True
    assert [run.failures for run in results] == [[] for _ in scenario["runs"]]
    assert [run.langs for run in results] == [["hi"]] * len(scenario["runs"])


def test_the_hindi_file_pins_english_with_the_code_en_one_proposal_r01_for_the_paste_and_the_422():
    scenario = load_suite(LIVE_DIR / "hindi.yaml")
    rent, paste, http = scenario["runs"]

    assert all(turn.get("lang") == "detect" for turn in rent["turns"] + paste["turns"])
    assert rent["expected"]["lang"] == "en" and rent["expected"]["ledger"] == ["proposal", "decision"]
    assert paste["expected"]["lang"] == "en" and paste["expected"]["rule_ids"] == ["R01"]
    assert http["turns"][0]["http"]["json"]["lang"] == "hi"
    assert http["turns"][0]["expect"] == {"status": 422}


def test_the_ordinary_evidence_run_never_reads_the_live_only_files():
    ids = {entry.id for entry in evaluate(SUITES_DIR, SCENARIOS_DIR)}

    assert not ids & {load_suite(path)["id"] for path in LIVE_DIR.glob("*.yaml")}


def test_an_error_the_harness_raises_keeps_its_words_in_a_live_run(tmp_path):
    # The harness's own errors hold no prompt and no provider words, so a live report can say what went wrong.
    scenario = {**SCRIPTED, "runs": [{**SCRIPTED["runs"][0], "turns": [*SCRIPTED["runs"][0]["turns"], {"user": "Yes", "confirm": "latest"}]}]}
    suites = _suites(tmp_path, scenario)

    [entry] = _live(suites, _provider(*ANSWERS, _say("Not now.")))

    assert entry.runs[0].failures[-1] == "error: ScenarioError: confirm 'latest' names a reply without a confirmation"
