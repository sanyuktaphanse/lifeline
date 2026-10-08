import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from contracts.schemas import AgentReply, Mandate, Message, Plan, RescueReply, Role, Source, StandingEvent, ToolCall
from core.agent import ANCHOR_KIND, AgentLoop
from core.anchor_local import LocalSignedAnchor
from core.council import VOICES, FiveVoiceCouncil
from core.fake_adapter import FakeModelAdapter
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.standing import RUN_WINDOW_AFTER_DUE, next_occurrence
from rails.fake_rail import FakeRail, scripted_traces
from rails.inbound import inbound_from_fixture, seed_inbound
from rails.sim.cn_bank_remit import CnBankRemitSimRail
from rails.sim.pix import PixSimRail
from rails.sim.upi_paynow import UpiPayNowSimRail
from rails.fake_router import FakeRouter

ROOT = Path(__file__).resolve().parent.parent
SUITES_DIR = ROOT / "suites"
SCENARIOS_DIR = SUITES_DIR / "scenarios"
REPORT_PATH = ROOT / "evidence" / "report.md"
# Each run anchors into a directory of its own under this one, removed when the run ends, so no
# scenario writes into data/. Git ignores it, and it stays inside the repository, as CLAUDE.md rule 9 asks.
RUNS_TMP = ROOT / ".harness_tmp"
SUITES = (("tasks", "tasks.yaml"), ("attacks", "attacks.yaml"))
PASSED, FAILED, NOT_AUTOMATED = "passed", "failed", "not automated"
TIERS = ("T0", "T1", "T2", "T3")
# A run's text checks add to the scenario's; every other expectation in a run replaces the scenario's.
TEXT_CHECKS = ("must_contain", "must_not_contain", "must_not_match")
# The ledger expectation lists the action trail; turn entries only count a turn's messages and anchor
# entries only record the head, so neither is part of it.
TURN_KIND = "turn"
# Expectations judged against the run itself, not against the final reply.
RUN_CHECKS = ("ledger", "anchors", "notes", "family_notice", "must_not_contain", "must_not_match", "verify")
# A turn whose language is this one is built without a language, so the loop detects it.
DETECT = "detect"
# The only tool whose action reaches a rail, so the only one a fail_once entry needs to name.
PROPOSE_TRANSFER = "propose_transfer"

# Fixtures for scenarios, not published limits. Source: this file, matching fixtures/demo_user.yaml.
USER = "student_001"
DEMO_FIXTURE = ROOT / "fixtures" / "demo_user.yaml"
FIXTURE_MANDATE: dict[str, Any] = {
    "id": "mandate-student_001-v1",
    "user_id": USER,
    "currency": "SGD",
    "per_txn_limit": "1500",
    "daily_limit": "2500",
    "allowed_payees": ["landlord_sp", "self_sg"],
    "allowed_corridors": ["SG>BR", "SG>SG"],
    "allowed_purposes": ["rent", "emergency"],
    # Fixture: the student's own account was added long before, so it is past its cooling period.
    "payee_added_at": {"self_sg": "2026-01-01T00:00:00Z"},
}
# A rescue turn starts a rescue or takes its next step.
RESCUE_TURNS = ("start", "step")
FIXTURE_BALANCES = {"SGD": "2300", "BRL": "150"}
# The rails a scenario can ask for, and which of them is a simulation. Source: this file, matching api/main.py.
FIXTURE_RAILS = {
    "wise": False,
    "bank_wire": False,
    "sim_pix": True,
    "revolut": False,
    "upi_paynow_sim": True,
    "cn_bank_remit_sim": True,
}
# The simulated rails, each built with the script a scenario chooses in fixtures.rail_scripts.
SIM_RAILS = {"upi_paynow_sim": UpiPayNowSimRail, "sim_pix": PixSimRail, "cn_bank_remit_sim": CnBankRemitSimRail}
# Long enough to cover a standing run that falls due up to two months ahead.
FIXTURE_VALIDITY = timedelta(days=70)


@dataclass
class RunResult:
    langs: list[str]
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass
class EntryResult:
    suite: str
    id: str
    title: str
    tier: str | None
    langs: list[str]
    status: str
    runs: list[RunResult] = field(default_factory=list)
    note: str | None = None


def load_suite(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def _mandate(overrides: dict[str, Any]) -> Mandate:
    now = datetime.now(timezone.utc)
    fields = {
        **FIXTURE_MANDATE,
        "valid_from": now - FIXTURE_VALIDITY,
        "valid_until": now + FIXTURE_VALIDITY,
        **overrides,
    }
    return Mandate.model_validate(fields)


def _plan(fixtures: dict[str, Any]) -> Plan:
    """The demo plan from fixtures/demo_user.yaml, with a scenario's plan replacing it key by key."""
    demo = load_suite(DEMO_FIXTURE)["plan"]
    return Plan.model_validate({**demo, **fixtures.get("plan", {})})


def _fail_once_keys(entries: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Build, per rail, the idempotency keys the loop will use for the proposals that must fail once.

    The loop's key is the student, the letter t and the turn number, the tool, and the call number
    within that turn, as `_run_tool` in `core/agent.py` builds it. An entry that the helper cannot
    express names its `key` in full instead.
    """
    keys: dict[str, set[str]] = {}
    for entry in entries:
        key = entry.get("key") or f"{USER}:t{entry['turn']}:{entry.get('tool', PROPOSE_TRANSFER)}:{entry['call']}"
        keys.setdefault(entry["rail"], set()).add(key)
    return keys


def _rails(fixtures: dict[str, Any]) -> dict[str, Any]:
    names = fixtures.get("rails", list(FIXTURE_RAILS))
    unknown = [name for name in names if name not in FIXTURE_RAILS]
    if unknown:
        raise ValueError(f"rails names {unknown}, which is not among {sorted(FIXTURE_RAILS)}")
    traces = scripted_traces(fixtures.get("traces"))
    failing = _fail_once_keys(fixtures.get("fail_once", []))
    scripts = fixtures.get("rail_scripts", {})
    stray = sorted({*traces, *failing, *scripts} - set(names))
    if stray:
        raise ValueError(f"traces, fail_once or rail_scripts name rails {stray}, which this scenario does not build")
    scripted_fakes = sorted({*traces, *failing} & set(SIM_RAILS))
    if scripted_fakes:
        raise ValueError(f"traces and fail_once script fake rails; {scripted_fakes} are simulated rails, which run rail_scripts")
    not_simulated = sorted(set(scripts) - set(SIM_RAILS))
    if not_simulated:
        raise ValueError(f"rail_scripts names {not_simulated}, which are not simulated rails")
    demo = load_suite(DEMO_FIXTURE)
    # What a simulated rail is built with beyond its script, from the scenario or else the demo fixture.
    built_with = {
        "sim_pix": {"pix_key_on_file": fixtures.get("pix_key_on_file", demo["pix_key_on_file"])},
        "cn_bank_remit_sim": {
            "documents_on_file": fixtures.get("documents_on_file", demo["documents_on_file"]),
            "quota_position_known": fixtures.get("quota_position_known", demo["quota_position_known"]),
        },
    }
    return {
        name: SIM_RAILS[name](script=scripts.get(name, "normal"), **built_with.get(name, {}))
        if name in SIM_RAILS
        else FakeRail(
            traces.get(name),
            fail_once_keys=failing.get(name, ()),
            name=name,
            simulated=FIXTURE_RAILS[name],
        )
        for name in names
    }


def _council(fixtures: dict[str, Any]) -> FiveVoiceCouncil | None:
    """The council a scenario asks for, with one scripted reply per voice.

    Without `fixtures.council` the loop is built with no council at all, which is how every
    scenario written before the council ran and still runs.
    """
    scripted = fixtures.get("council")
    if scripted is None:
        return None
    if len(scripted) != len(VOICES):
        raise ValueError(
            f"council scripts {len(scripted)} voices, and it needs one for each of "
            f"{', '.join(VOICES)}"
        )
    return FiveVoiceCouncil(FakeModelAdapter(scripted))


def _response(response: dict[str, Any], number: int) -> Message:
    calls = [
        ToolCall(id=call.get("id", f"toolu_{number:02d}_{index}"), name=call["name"], arguments=call.get("arguments", {}))
        for index, call in enumerate(response.get("calls", []), start=1)
    ]
    return Message(
        role=Role.ASSISTANT, text=response.get("text", ""), tool_calls=calls, provider="fake", model="fake-model"
    )


def reply_kind(reply: AgentReply) -> str:
    if reply.receipt is not None:
        return "receipt"
    if reply.freeze is not None:
        return "freeze"
    if reply.confirmation is not None:
        return "confirmation"
    if reply.decision is not None and not reply.decision.allowed:
        return "refusal"
    return "answer"


def _judge(where: str, reply: AgentReply, expect: dict[str, Any]) -> list[str]:
    failures = []
    if "reply" in expect and reply_kind(reply) != expect["reply"]:
        failures.append(f"{where}: reply was {reply_kind(reply)}, expected {expect['reply']}")
    if "rule_ids" in expect:
        rule_ids = reply.decision.rule_ids if reply.decision else []
        if rule_ids != expect["rule_ids"]:
            failures.append(f"{where}: rule ids were {rule_ids}, expected {expect['rule_ids']}")
    if "warning_key" in expect:
        warning = reply.confirmation.warning_key if reply.confirmation else None
        if warning != expect["warning_key"]:
            failures.append(f"{where}: warning key was {warning}, expected {expect['warning_key']}")
    if "lang" in expect and reply.lang != expect["lang"]:
        failures.append(f"{where}: reply language was {reply.lang}, expected {expect['lang']}")
    if "rescue_state" in expect or "do_now" in expect:
        progress = reply.rescue if isinstance(reply, RescueReply) else None
        state = progress.state_after.value if progress and progress.state_after else None
        if "rescue_state" in expect and state != expect["rescue_state"]:
            failures.append(f"{where}: rescue state was {state}, expected {expect['rescue_state']}")
        do_now = progress.do_now if progress else None
        if "do_now" in expect and do_now != expect["do_now"]:
            failures.append(f"{where}: do_now was {do_now}, expected {expect['do_now']}")
    for text in expect.get("must_contain", []):
        if text not in reply.text:
            failures.append(f"{where}: reply text does not contain {text!r}")
    for text in expect.get("must_not_contain", []):
        if text in reply.text:
            failures.append(f"{where}: reply text contains {text!r}")
    # A regular expression no reply may match, such as a digit run longer than four. Replies only:
    # the ledger holds hashes, whose digits a pattern like that would find.
    for pattern in expect.get("must_not_match", []):
        if re.search(pattern, reply.text):
            failures.append(f"{where}: reply text matches {pattern!r}")
    return failures


def _model_saw(where: str, calls: list[tuple[list[Message], list[dict[str, Any]]]], expect: dict[str, Any]) -> list[str]:
    wanted = expect.get("model_saw", [])
    if not wanted:
        return []
    if not calls:
        return [f"{where}: the model was not called, so it saw nothing"]
    seen = "\n".join(message.text for message in calls[0][0])
    return [f"{where}: the model did not receive {text!r}" for text in wanted if text not in seen]


def _run_due_time(mandate: Mandate, when: str) -> datetime:
    standing = mandate.standing_mandates[-1]
    now = datetime.now(timezone.utc)
    period, due = next_occurrence(standing.schedule, now)
    if due - timedelta(hours=standing.notice_hours) <= now + timedelta(minutes=1):
        period, due = next_occurrence(standing.schedule, due + RUN_WINDOW_AFTER_DUE)
    notice_at = due - timedelta(hours=standing.notice_hours)
    if when == "notice":
        return notice_at + timedelta(minutes=1)
    if when == "after_cancel_window":
        return notice_at + timedelta(hours=standing.cancel_window_hours, minutes=2)
    raise ValueError(f"run_due must be notice or after_cancel_window, not {when!r}")


def _judge_events(where: str, events: list[StandingEvent], expected: list[dict[str, Any]]) -> list[str]:
    kinds = [event.kind for event in events]
    if len(events) != len(expected):
        return [f"{where}: events were {kinds}, expected {[wanted.get('kind') for wanted in expected]}"]
    failures = []
    for event, wanted in zip(events, expected):
        view = {
            "kind": event.kind,
            "standing_mandate_id": event.standing_mandate_id,
            "period": event.period,
            "rule_ids": event.decision.rule_ids if event.decision else [],
            "tier": event.decision.tier.value if event.decision else None,
            "receipt_mandate_ref": event.receipt.mandate_ref if event.receipt else None,
            "receipt_standing_mandate_id": event.receipt.standing_mandate_id if event.receipt else None,
        }
        failures += [
            f"{where}: event {name} was {view.get(name)!r}, expected {value!r}"
            for name, value in wanted.items()
            if view.get(name) != value
        ]
    return failures


def _token(confirm: Any, replies: list[AgentReply]) -> str:
    if confirm == "latest":
        source = next((reply for reply in reversed(replies) if reply.confirmation), None)
    else:
        source = replies[int(confirm) - 1]
    if source is None or source.confirmation is None:
        raise ValueError(f"confirm {confirm!r} names a reply without a confirmation")
    return source.confirmation.confirmation_token


def _turn_lang(turn: dict[str, Any], run: dict[str, Any]) -> str:
    """The language of a turn: its own, or the run's, which is also what a detect turn is reported as."""
    lang = turn.get("lang", run["lang"])
    return run["lang"] if lang == DETECT else lang


def _message(turn: dict[str, Any], run: dict[str, Any]) -> Message:
    """The student's message. A detect turn passes no language, so the loop detects it from the text."""
    fields: dict[str, Any] = {
        "role": Role.USER,
        "text": turn.get("user", ""),
        "source": Source(turn.get("source", Source.USER_TURN.value)),
    }
    lang = turn.get("lang", run["lang"])
    if lang != DETECT:
        fields["lang"] = lang
    return Message(**fields)


def run_scenario_run(scenario: dict[str, Any], run: dict[str, Any]) -> RunResult:
    RUNS_TMP.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNS_TMP) as anchors_dir:
        return _run_scenario_run(scenario, run, Path(anchors_dir) / "anchors.jsonl")


def _run_scenario_run(scenario: dict[str, Any], run: dict[str, Any], anchors_path: Path) -> RunResult:
    result = RunResult(langs=list(dict.fromkeys(_turn_lang(turn, run) for turn in run["turns"])))
    shared, own = scenario.get("expected", {}), run.get("expected", {})
    expected = {**shared, **own}
    for key in TEXT_CHECKS:
        expected[key] = [*shared.get(key, []), *own.get(key, [])]
    try:
        responses = [
            _response(response, number)
            for number, response in enumerate(
                (response for turn in run["turns"] for response in turn.get("model", [])), start=1
            )
        ]
        ledger = HashChainLedger()
        adapter = FakeModelAdapter(responses)
        # A run's own fixtures replace the scenario's key by key, so two runs of one entry can
        # differ in what they are given, such as a council that splits its vote differently.
        fixtures = {**scenario.get("fixtures", {}), **run.get("fixtures", {})}
        balances = {currency: Decimal(amount) for currency, amount in fixtures.get("balances", FIXTURE_BALANCES).items()}
        mandates = {USER: _mandate(fixtures.get("mandate", {}))}
        rails = _rails(fixtures)
        inbound = seed_inbound(rails, inbound_from_fixture(fixtures.get("inbound_receipts"), rails))
        loop = AgentLoop(
            adapter=adapter,
            engine=DeterministicMandateEngine(),
            ledger=ledger,
            router=FakeRouter(),
            rails=rails,
            mandates=mandates,
            balances={USER: balances},
            pending={},
            council=_council(fixtures),
            plans={USER: _plan(fixtures)},
            inbound_receipts={USER: inbound},
            anchor=LocalSignedAnchor(anchors_path),
        )
        replies: list[AgentReply] = []
        for number, turn in enumerate(run["turns"], start=1):
            if "run_due" in turn:
                events = loop.run_due_standing_mandates(_run_due_time(mandates[USER], turn["run_due"]))
                result.failures += _judge_events(f"turn {number}", events, turn.get("expect", {}).get("events", []))
                continue
            if "tamper" in turn:
                # entries() returns copies, so the stored list is reached the way tests/test_ledger.py does.
                ledger._entries[turn["tamper"]["seq"] - 1].payload.update(turn["tamper"]["payload"])
                continue
            message = _message(turn, run)
            if "rescue" in turn:
                token = turn.get("token") or (_token(turn["confirm"], replies) if "confirm" in turn else None)
                if turn["rescue"] not in RESCUE_TURNS:
                    raise ValueError(f"rescue must be start or step, not {turn['rescue']!r}")
                if turn["rescue"] == "start":
                    reply = loop.rescue_start(USER, turn["trigger"], message)
                else:
                    reply = loop.rescue_step(USER, message, confirmation_token=token)
                replies.append(reply)
                result.failures += _judge(f"turn {number}", reply, turn.get("expect", {}))
                continue
            pasted = (
                Message(role=Role.USER, text=turn["pasted"], source=Source.PASTED_TEXT)
                if turn.get("pasted")
                else None
            )
            token = turn.get("token") or (_token(turn["confirm"], replies) if "confirm" in turn else None)
            before = len(adapter.calls)
            reply = loop.handle(USER, message, confirmation_token=token, pasted=pasted)
            replies.append(reply)
            result.failures += _judge(f"turn {number}", reply, turn.get("expect", {}))
            result.failures += _model_saw(f"turn {number}", adapter.calls[before:], turn.get("expect", {}))
    except Exception as error:  # anti-pattern: SILENT-EXCEPT ok, the error becomes a failed run in the report
        result.failures.append(f"error: {type(error).__name__}: {error}")
        return result
    final = {key: value for key, value in expected.items() if key not in RUN_CHECKS}
    result.failures += _judge("final reply", replies[-1], final)
    for number, reply in enumerate(replies, start=1):
        result.failures += _judge(
            f"turn {number}",
            reply,
            {name: expected.get(name, []) for name in ("must_not_contain", "must_not_match")},
        )
    kinds = [entry.kind for entry in ledger.entries() if entry.kind not in (TURN_KIND, ANCHOR_KIND)]
    if "ledger" in expected and kinds != expected["ledger"]:
        result.failures.append(f"ledger kinds were {kinds}, expected {expected['ledger']}")
    # Anchor entries are left out of the trail, so a scenario asserts them by their count.
    anchors = sum(entry.kind == ANCHOR_KIND for entry in ledger.entries())
    if "anchors" in expected and anchors != expected["anchors"]:
        result.failures.append(f"anchor entries were {anchors}, expected {expected['anchors']}")
    notes = [entry.payload.get("kind") for entry in ledger.entries() if entry.kind == "note"]
    if "notes" in expected and notes != expected["notes"]:
        result.failures.append(f"notes were {notes}, expected {expected['notes']}")
    if "family_notice" in expected:
        notices = [e.payload["text"] for e in ledger.entries() if e.kind == "note" and e.payload.get("kind") == "family_notice"]
        if not notices:
            result.failures.append("no family notice was written")
        for text in expected["family_notice"] if notices else []:
            if text not in notices[-1]:
                result.failures.append(f"family notice does not contain {text!r}")
    ledger_text = json.dumps([entry.payload for entry in ledger.entries()], ensure_ascii=False, default=str)
    for text in expected.get("must_not_contain", []):
        if text in ledger_text:
            result.failures.append(f"ledger contains {text!r}")
    broken = ledger.verify()
    if "verify" in expected:
        if broken != expected["verify"]:
            result.failures.append(f"ledger verify returned {broken}, expected a break at entry {expected['verify']}")
    elif broken is not None:
        result.failures.append(f"ledger chain breaks at entry {broken}")
    return result


def _run_file(path: Path, entry_id: str) -> tuple[list[RunResult], str | None]:
    try:
        scenario = load_suite(path)
    except yaml.YAMLError as error:  # anti-pattern: SILENT-EXCEPT ok, the parse error fails the entry in the report
        return [RunResult([], [f"scenario file cannot be read: {error}"])], None
    if scenario.get("id") != entry_id:
        return [RunResult([], [f"scenario id {scenario.get('id')!r} does not match {entry_id}"])], scenario.get("note")
    runs = [run_scenario_run(scenario, run) for run in scenario.get("runs", [])]
    return runs or [RunResult([], ["scenario has no runs"])], scenario.get("note")


def evaluate(suites_dir: Path = SUITES_DIR, scenarios_dir: Path | None = None) -> list[EntryResult]:
    scenarios_dir = suites_dir / "scenarios" if scenarios_dir is None else scenarios_dir
    results = []
    for suite, filename in SUITES:
        for entry in load_suite(suites_dir / filename):
            result = EntryResult(
                suite=suite,
                id=entry["id"],
                title=entry["title"],
                tier=entry.get("tier"),
                langs=list(entry.get("langs", [])),
                status=NOT_AUTOMATED,
            )
            path = scenarios_dir / f"{entry['id']}.yaml"
            if path.exists():
                result.runs, result.note = _run_file(path, entry["id"])
                result.status = PASSED if all(run.passed for run in result.runs) else FAILED
            results.append(result)
    return results


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def _count_table(title: str, key: str, groups: dict[str, list[EntryResult]]) -> list[str]:
    lines = [f"## {title}", "", _row(key, "Entries", "Passed", "Failed", "Not automated"), _row(*["---"] * 5)]
    for name, entries in groups.items():
        counts = Counter(entry.status for entry in entries)
        lines.append(_row(name, len(entries), counts[PASSED], counts[FAILED], counts[NOT_AUTOMATED]))
    return lines + [""]


def render_report(results: list[EntryResult], commit: str, generated_at: datetime) -> str:
    lines = [
        "# Lifeline evidence report",
        "",
        f"Generated by `core/harness.py` at {generated_at.isoformat(timespec='seconds')} from commit `{commit}`.",
        "Every number and row below is computed from `suites/` and `suites/scenarios/`. "
        "An entry without a scenario is not automated and is never counted as passed.",
        "",
    ]
    suites = {suite: [r for r in results if r.suite == suite] for suite, _ in SUITES}
    lines += _count_table("By suite", "Suite", suites)
    tiers = {tier: [r for r in suites["tasks"] if r.tier == tier] for tier in TIERS}
    lines += _count_table("By tier, tasks", "Tier", tiers)
    runs = [run for result in results for run in result.runs]
    lines += ["## By language, runs", "", _row("Language", "Runs", "Passed", "Failed"), _row(*["---"] * 4)]
    for lang in sorted({lang for run in runs for lang in run.langs}):
        chosen = [run for run in runs if lang in run.langs]
        passed = sum(run.passed for run in chosen)
        lines.append(_row(lang, len(chosen), passed, len(chosen) - passed))
    lines += ["", "## Automated entries", "", _row("Id", "Suite", "Tier", "Title", "Result", "Languages run", "Languages declared", "Note"), _row(*["---"] * 8)]
    for result in results:
        if result.status != NOT_AUTOMATED:
            run_langs = ", ".join(dict.fromkeys(lang for run in result.runs for lang in run.langs))
            lines.append(
                _row(result.id, result.suite, result.tier or "", result.title, result.status, run_langs, ", ".join(result.langs), result.note or "")
            )
    failed = [result for result in results if result.status == FAILED]
    if failed:
        lines += ["", "## Failures", ""]
        for result in failed:
            for run in result.runs:
                for failure in run.failures:
                    lines.append(f"1. {result.id}, run in {', '.join(run.langs) or 'no language'}: {failure}")
    lines += ["", "## Not automated", "", _row("Id", "Suite", "Tier", "Title", "Result"), _row(*["---"] * 5)]
    for result in results:
        if result.status == NOT_AUTOMATED:
            lines.append(_row(result.id, result.suite, result.tier or "", result.title, result.status))
    return "\n".join(lines) + "\n"


def _commit() -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return f"unknown, git failed: {error}"
    return f"{head}, with uncommitted changes" if dirty else head


def main() -> int:
    results = evaluate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results, _commit(), datetime.now(timezone.utc)), encoding="utf-8")
    counts = Counter(result.status for result in results)
    print(
        f"{REPORT_PATH.relative_to(ROOT)}: {counts[PASSED]} passed, {counts[FAILED]} failed, "
        f"{counts[NOT_AUTOMATED]} not automated"
    )
    return 1 if counts[FAILED] else 0


if __name__ == "__main__":
    sys.exit(main())
