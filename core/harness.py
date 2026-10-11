import argparse
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from contracts.schemas import (
    AgentReply,
    Mandate,
    Message,
    Plan,
    ReceiptStatus,
    RescueReply,
    Role,
    Source,
    StandingEvent,
    Tier,
    ToolCall,
)
from contracts.interfaces import ModelAdapter
from core.agent import ANCHOR_KIND, REDACTION_MARKER, AgentLoop
from core.anchor_local import LocalSignedAnchor
from core.council import VOICES, FiveVoiceCouncil
from core.fake_adapter import FakeModelAdapter
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.model_adapter import (
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_PROVIDER,
    PROVIDERS,
    ModelAdapterError,
    ProviderModelAdapter,
    api_key_variable,
    council_env,
    environment,
    model_name,
)
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
# The stranger runs: scenarios from each stranger test, played as a group apart from the suite entries, so the
# entries' counts keep their meaning. Source: docs/decisions.md, decision 147.
STRANGER_DIR = SCENARIOS_DIR / "stranger"
EXPECTED_FAILING = "expected failing"
FLAG_TO_REMOVE = "passes but flagged"
REPORT_PATH = ROOT / "evidence" / "report.md"
# Scenarios only the live mode reads, such as a language the loop cannot write in. The ordinary run never opens it.
LIVE_DIR = SUITES_DIR / "live"
LIVE_SUITE = "live"
SWAP_REPORT_PATH = ROOT / "evidence" / "report-swap.md"
# Empty or all runs every scenario marked live. Source: docs/decisions.md, decision 135.
LIVE_LIMIT_VARIABLE = "LIVE_SCENARIO_LIMIT"
LIVE_LIMIT_ALL = ("", "all")
# How long one live model call may take before it fails its run, so a hung call never stalls a live run.
# Source: docs/decisions.md, decision 142.
LIVE_CALL_TIMEOUT_SECONDS = 60
# Each run anchors into a directory of its own under this one, removed when the run ends, so no
# scenario writes into data/. Git ignores it, and it stays inside the repository, as CLAUDE.md rule 9 asks.
RUNS_TMP = ROOT / ".harness_tmp"
SUITES = (("tasks", "tasks.yaml"), ("attacks", "attacks.yaml"))
PASSED, FAILED, NOT_AUTOMATED = "passed", "failed", "not automated"
# A live run whose every expectation was scripted model text is skipped: nothing in it was judged.
SKIPPED = "skipped"
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


class ScenarioError(ValueError):
    """A scenario the harness cannot play as written. Its words come from the scenario, never from a provider."""


@dataclass
class RunResult:
    langs: list[str]
    failures: list[str] = field(default_factory=list)
    # How many checks were judged, and in live mode the scripted text checks that were not.
    checked: int = 0
    skipped: list[str] = field(default_factory=list)
    # The text of every reply, kept so a live failure shows what the model did. Each passed the reply guard.
    replies: list[str] = field(default_factory=list)
    # The action trail as the ledger holds it, and in live mode how many read triples were set aside before
    # the ledger kinds were compared.
    trail: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    stripped: int = 0

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def status(self) -> str:
        if self.failures:
            return FAILED
        return PASSED if self.checked else SKIPPED


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


@dataclass
class StrangerResult:
    """One file of a stranger run, judged against its expected_failing flag."""

    file: str
    id: str
    task: str
    run: str
    expected_failing: bool
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


# A fixtures.user block may name a fixture file in fixtures/ by its plain name, such as demo_parent.
FIXTURE_NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass
class _Who:
    """Who a run is: the user id, their mandate, balances, plan, and Chinese cards."""

    user_id: str
    mandate: Mandate
    balances: dict[str, Decimal]
    plan: Plan
    chinese_cards: list[dict[str, Any]]


def _who(fixtures: dict[str, Any]) -> _Who:
    """The demo student, or the user a scenario's fixtures.user names, written inline or by fixture file.

    A user block holds a user id, a mandate with its own currency, limits, payees, corridors and purposes,
    balances and a plan. A scenario's mandate and plan still replace the block's key by key.
    """
    block = fixtures.get("user")
    if block is None:
        balances = fixtures.get("balances", FIXTURE_BALANCES)
        cards = fixtures["chinese_cards"] if "chinese_cards" in fixtures else load_suite(DEMO_FIXTURE).get("chinese_cards")
        return _Who(
            USER,
            _mandate(fixtures.get("mandate", {})),
            {currency: Decimal(amount) for currency, amount in balances.items()},
            _plan(fixtures),
            cards or [],
        )
    if "fixture" in block:
        name = str(block["fixture"])
        if not FIXTURE_NAME.fullmatch(name):
            raise ScenarioError(f"fixtures.user names fixture {name!r}, which is not a plain fixture name")
        block = {**load_suite(ROOT / "fixtures" / f"{name}.yaml"), **{k: v for k, v in block.items() if k != "fixture"}}
    now = datetime.now(timezone.utc)
    mandate = Mandate.model_validate(
        {
            "user_id": block["user_id"],
            "valid_from": now - FIXTURE_VALIDITY,
            "valid_until": now + FIXTURE_VALIDITY,
            **block["mandate"],
            **fixtures.get("mandate", {}),
        }
    )
    return _Who(
        block["user_id"],
        mandate,
        {currency: Decimal(str(amount)) for currency, amount in fixtures.get("balances", block["balances"]).items()},
        Plan.model_validate({**block["plan"], **fixtures.get("plan", {})}),
        fixtures.get("chinese_cards", block.get("chinese_cards")) or [],
    )


def _fail_once_keys(entries: list[dict[str, Any]], user_id: str = USER) -> dict[str, set[str]]:
    """Build, per rail, the idempotency keys the loop will use for the proposals that must fail once.

    The loop's key is the student, the letter t and the turn number, the tool, and the call number
    within that turn, as `_run_tool` in `core/agent.py` builds it. An entry that the helper cannot
    express names its `key` in full instead.
    """
    keys: dict[str, set[str]] = {}
    for entry in entries:
        key = entry.get("key") or f"{user_id}:t{entry['turn']}:{entry.get('tool', PROPOSE_TRANSFER)}:{entry['call']}"
        keys.setdefault(entry["rail"], set()).add(key)
    return keys


def _rails(fixtures: dict[str, Any], user_id: str = USER) -> dict[str, Any]:
    names = fixtures.get("rails", list(FIXTURE_RAILS))
    unknown = [name for name in names if name not in FIXTURE_RAILS]
    if unknown:
        raise ScenarioError(f"rails names {unknown}, which is not among {sorted(FIXTURE_RAILS)}")
    traces = scripted_traces(fixtures.get("traces"))
    failing = _fail_once_keys(fixtures.get("fail_once", []), user_id)
    scripts = fixtures.get("rail_scripts", {})
    # Fixture: the status each fake rail issues receipts at, completed unless the scenario chooses one.
    statuses = {name: ReceiptStatus(status) for name, status in (fixtures.get("receipt_status") or {}).items()}
    stray = sorted({*traces, *failing, *scripts, *statuses} - set(names))
    if stray:
        raise ScenarioError(f"traces, fail_once, rail_scripts or receipt_status name rails {stray}, which this scenario does not build")
    scripted_fakes = sorted({*traces, *failing, *statuses} & set(SIM_RAILS))
    if scripted_fakes:
        raise ScenarioError(f"traces and fail_once script fake rails; {scripted_fakes} are simulated rails, which run rail_scripts")
    not_simulated = sorted(set(scripts) - set(SIM_RAILS))
    if not_simulated:
        raise ScenarioError(f"rail_scripts names {not_simulated}, which are not simulated rails")
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
            issue_status=statuses.get(name, ReceiptStatus.COMPLETED),
        )
        for name in names
    }


def _council(fixtures: dict[str, Any], live: "LiveProvider | None" = None) -> FiveVoiceCouncil | None:
    """The council a scenario asks for, with one scripted reply per voice for each deliberation.

    Without `fixtures.council` the loop is built with no council at all, which is how every
    scenario written before the council ran and still runs.
    """
    scripted = fixtures.get("council")
    if scripted is None:
        return None
    # One reply for each voice, in the order of VOICES, for each deliberation the run convenes, consumed in
    # order: a run whose rent and allowance both escalate scripts ten.
    if not scripted or len(scripted) % len(VOICES):
        raise ScenarioError(
            f"council scripts {len(scripted)} voices, and it needs one for each of "
            f"{', '.join(VOICES)} in every deliberation"
        )
    if live is not None:
        return FiveVoiceCouncil(live.adapter(council=True))
    return FiveVoiceCouncil(FakeModelAdapter(scripted))


@dataclass
class _Checks:
    """The checks of one run as they are judged.

    In live mode `scripted` holds every word the scenario's script gives the model and the council, and a
    text a run must find that appears there is scripted model text: only the script could have produced it,
    so it is skipped and counted as skipped, never as passed. In the scripted mode `scripted` is None.
    """

    scripted: str | None = None
    checked: int = 0
    skipped: list[str] = field(default_factory=list)

    def keep(self, where: str, name: str, text: str) -> bool:
        if self.scripted is not None and text in self.scripted:
            self.skipped.append(f"{where}: {name} {text!r} is scripted model text")
            return False
        self.checked += 1
        return True


def _read_key(kind: str, payload: dict[str, Any]) -> str | None:
    """The idempotency key an entry of a triple names, from its action or, for a decision, from the entry."""
    if kind == "decision":
        return payload.get("idempotency_key")
    return (payload.get("action") or {}).get("idempotency_key")


def strip_read_triples(trail: list[tuple[str, dict[str, Any]]]) -> tuple[list[str], int]:
    """The trail's kinds without the proposal, decision and execution of every allowed T0 action, and how many went.

    A triple is set aside only whole: three entries in a row, one key across all three, and a decision that
    allowed the action at T0. A refused read, a read with anything between its entries, and every action above
    T0 stay. Source: docs/decisions.md, decision 138.
    """
    kinds: list[str] = []
    stripped = 0
    index = 0
    while index < len(trail):
        window = trail[index : index + 3]
        if [kind for kind, _ in window] == ["proposal", "decision", "execution"]:
            keys = {_read_key(kind, payload) for kind, payload in window}
            decision = window[1][1].get("decision") or {}
            if len(keys) == 1 and None not in keys and decision.get("allowed") is True and decision.get("tier") == Tier.T0.value:
                stripped += 1
                index += 3
                continue
        kinds.append(trail[index][0])
        index += 1
    return kinds, stripped


def _scripted_text(run: dict[str, Any], fixtures: dict[str, Any]) -> str:
    """Everything a scenario's script would have the model or the council say in this run."""
    texts = [response.get("text", "") for turn in run["turns"] for response in turn.get("model", [])]
    texts += [voice if isinstance(voice, str) else json.dumps(voice, ensure_ascii=False) for voice in fixtures.get("council") or []]
    return "\n".join(texts)


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
    if reply.cancel is not None:
        return "cancel"
    if reply.confirmation is not None:
        return "confirmation"
    if reply.decision is not None and not reply.decision.allowed:
        return "refusal"
    return "answer"


def _judge(where: str, reply: AgentReply, expect: dict[str, Any], checks: _Checks | None = None) -> list[str]:
    checks = checks if checks is not None else _Checks()
    checks.checked += sum(
        name in expect for name in ("reply", "rule_ids", "warning_key", "lang", "rescue_state", "do_now")
    ) + len(expect.get("must_not_contain", [])) + len(expect.get("must_not_match", []))
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
        if checks.keep(where, "must_contain", text) and text not in reply.text:
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


def _model_saw(
    where: str,
    calls: list[tuple[list[Message], list[dict[str, Any]]]],
    expect: dict[str, Any],
    checks: _Checks | None = None,
) -> list[str]:
    checks = checks if checks is not None else _Checks()
    wanted = [text for text in expect.get("model_saw", []) if checks.keep(where, "model_saw", text)]
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
    raise ScenarioError(f"run_due must be notice or after_cancel_window, not {when!r}")


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
        raise ScenarioError(f"confirm {confirm!r} names a reply without a confirmation")
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


def run_scenario_run(scenario: dict[str, Any], run: dict[str, Any], live: "LiveProvider | None" = None) -> RunResult:
    RUNS_TMP.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNS_TMP) as run_dir:
        return _run_scenario_run(scenario, run, Path(run_dir), live)


def _http_turn(request: dict[str, Any], adapter: ModelAdapter, run_dir: Path) -> int:
    """Send one request to the API, built with this run's adapter and files of its own, and return its status.

    The API is imported here so the ordinary run, which sends no request, never builds it.
    """
    from fastapi.testclient import TestClient

    from api.main import create_app

    app = create_app(
        adapter=adapter,
        ledger_path=run_dir / "api_ledger.jsonl",
        conversations_path=run_dir / "api_conversations.jsonl",
        tick_seconds=None,
        anchor=LocalSignedAnchor(run_dir / "api_anchors.jsonl"),
    )
    with TestClient(app) as client:
        response = client.request(request.get("method", "POST"), request["path"], json=request.get("json"))
    return response.status_code


def _error_line(error: Exception, live: "LiveProvider | None") -> str:
    """How an error that ended a run is written. A live run writes the class, and for a provider failure the
    provider and the status, never the error's own words, which can hold a prompt or a provider's reply. A
    `ScenarioError` keeps its words, because the harness wrote them from the scenario."""
    if live is None:
        return f"error: {type(error).__name__}: {error}"
    if isinstance(error, ScenarioError):
        return f"error: {type(error).__name__}: {error}"
    if isinstance(error, ModelCallTimeout):
        return f"error: {type(error).__name__}, {error}"
    if isinstance(error, ModelAdapterError):
        return f"error: {type(error).__name__} from {error.provider or 'an unnamed provider'}, status {error.status_code or 'none'}"
    return f"error: {type(error).__name__}"


def _run_scenario_run(scenario: dict[str, Any], run: dict[str, Any], run_dir: Path, live: "LiveProvider | None" = None) -> RunResult:
    anchors_path = run_dir / "anchors.jsonl"
    result = RunResult(langs=list(dict.fromkeys(_turn_lang(turn, run) for turn in run["turns"])))
    shared, own = scenario.get("expected", {}), run.get("expected", {})
    expected = {**shared, **own}
    for key in TEXT_CHECKS:
        expected[key] = [*shared.get(key, []), *own.get(key, [])]
    # A run's own fixtures replace the scenario's key by key, so two runs of one entry can
    # differ in what they are given, such as a council that splits its vote differently.
    fixtures = {**scenario.get("fixtures", {}), **run.get("fixtures", {})}
    checks = _Checks(_scripted_text(run, fixtures) if live is not None else None)
    replies: list[AgentReply] = []
    try:
        ledger = HashChainLedger()
        if live is not None:
            # The scripted replies are not used: the live provider answers instead.
            adapter: Any = live.adapter(council=False)
        else:
            adapter = FakeModelAdapter(
                [
                    _response(response, number)
                    for number, response in enumerate(
                        (response for turn in run["turns"] for response in turn.get("model", [])), start=1
                    )
                ]
            )
        who = _who(fixtures)
        user = who.user_id
        mandates = {user: who.mandate}
        rails = _rails(fixtures, user)
        inbound = seed_inbound(rails, inbound_from_fixture(fixtures.get("inbound_receipts"), rails))
        loop = AgentLoop(
            adapter=adapter,
            engine=DeterministicMandateEngine(),
            ledger=ledger,
            router=FakeRouter(),
            rails=rails,
            mandates=mandates,
            balances={user: who.balances},
            pending={},
            council=_council(fixtures, live),
            plans={user: who.plan},
            inbound_receipts={user: inbound},
            anchor=LocalSignedAnchor(anchors_path),
            # A scenario's own Chinese cards replace the demo fixture's, which are a fixture too.
            chinese_cards={user: who.chinese_cards},
        )
        for number, turn in enumerate(run["turns"], start=1):
            if "http" in turn:
                status = _http_turn(turn["http"], adapter, run_dir)
                result.replies.append(f"HTTP status {status}")
                wanted = turn.get("expect", {}).get("status")
                if wanted is not None:
                    checks.checked += 1
                    if status != wanted:
                        result.failures.append(f"turn {number}: HTTP status was {status}, expected {wanted}")
                continue
            if "run_due" in turn:
                events = loop.run_due_standing_mandates(_run_due_time(mandates[user], turn["run_due"]))
                wanted_events = turn.get("expect", {}).get("events", [])
                checks.checked += len(wanted_events)
                result.failures += _judge_events(f"turn {number}", events, wanted_events)
                continue
            if "tamper" in turn:
                # entries() returns copies, so the stored list is reached the way tests/test_ledger.py does.
                ledger._entries[turn["tamper"]["seq"] - 1].payload.update(turn["tamper"]["payload"])
                continue
            message = _message(turn, run)
            if "rescue" in turn:
                token = turn.get("token") or (_token(turn["confirm"], replies) if "confirm" in turn else None)
                if turn["rescue"] not in RESCUE_TURNS:
                    raise ScenarioError(f"rescue must be start or step, not {turn['rescue']!r}")
                if turn["rescue"] == "start":
                    reply = loop.rescue_start(user, turn["trigger"], message)
                else:
                    reply = loop.rescue_step(user, message, confirmation_token=token)
                replies.append(reply)
                result.replies.append(reply.text)
                result.failures += _judge(f"turn {number}", reply, turn.get("expect", {}), checks)
                continue
            pasted = (
                Message(role=Role.USER, text=turn["pasted"], source=Source.PASTED_TEXT)
                if turn.get("pasted")
                else None
            )
            token = turn.get("token") or (_token(turn["confirm"], replies) if "confirm" in turn else None)
            before = len(adapter.calls)
            reply = loop.handle(user, message, confirmation_token=token, pasted=pasted)
            replies.append(reply)
            result.replies.append(reply.text)
            result.failures += _judge(f"turn {number}", reply, turn.get("expect", {}), checks)
            result.failures += _model_saw(f"turn {number}", adapter.calls[before:], turn.get("expect", {}), checks)
    except Exception as error:  # anti-pattern: SILENT-EXCEPT ok, the error becomes a failed run in the report
        result.failures.append(_error_line(error, live))
        result.checked, result.skipped = checks.checked, checks.skipped
        return result
    # In live mode the expected trail sets aside the reads the scripted run of the same scenario writes, so both
    # sides of the comparison hold only the kinds that change something.
    reference = run_scenario_run(scenario, run) if live is not None and "ledger" in expected else None
    try:
        return _judge_run(result, expected, replies, ledger, checks, reference)
    finally:
        result.checked, result.skipped = checks.checked, checks.skipped


def _judge_run(
    result: RunResult,
    expected: dict[str, Any],
    replies: list[AgentReply],
    ledger: HashChainLedger,
    checks: _Checks,
    reference: RunResult | None = None,
) -> RunResult:
    """The checks made once every turn has run: the final reply, every reply, and the ledger.

    `reference` is the scripted run of the same scenario, given only in live mode, where reads are set aside on
    both sides before the ledger kinds are compared. The scripted mode compares the trail exactly.
    """
    final = {key: value for key, value in expected.items() if key not in RUN_CHECKS}
    if replies:
        result.failures += _judge("final reply", replies[-1], final, checks)
    elif any(final.values()):
        result.failures.append("final reply: the run sent no message, so there is no reply to judge")
    for number, reply in enumerate(replies, start=1):
        result.failures += _judge(
            f"turn {number}",
            reply,
            {name: expected.get(name, []) for name in ("must_not_contain", "must_not_match")},
            checks,
        )
    checks.checked += sum(name in expected for name in ("ledger", "anchors", "notes", "verify"))
    result.trail = [(entry.kind, entry.payload) for entry in ledger.entries() if entry.kind not in (TURN_KIND, ANCHOR_KIND)]
    kinds = [kind for kind, _ in result.trail]
    wanted = expected.get("ledger")
    if reference is not None:
        kinds, result.stripped = strip_read_triples(result.trail)
        # The expectation is the scripted trail's kinds, so its reads are found there; an expectation the
        # scripted run does not meet is compared as written.
        if [kind for kind, _ in reference.trail] == wanted:
            wanted = strip_read_triples(reference.trail)[0]
    if "ledger" in expected and kinds != wanted:
        result.failures.append(f"ledger kinds were {kinds}, expected {wanted}")
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
            if checks.keep("family notice", "family_notice", text) and text not in notices[-1]:
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


def _run_file(path: Path, entry_id: str, live: "LiveProvider | None" = None) -> tuple[list[RunResult], str | None]:
    try:
        scenario = load_suite(path)
    except yaml.YAMLError as error:  # anti-pattern: SILENT-EXCEPT ok, the parse error fails the entry in the report
        return [RunResult([], [f"scenario file cannot be read: {error}"])], None
    if scenario.get("id") != entry_id:
        return [RunResult([], [f"scenario id {scenario.get('id')!r} does not match {entry_id}"])], scenario.get("note")
    runs = [run_scenario_run(scenario, run, live) for run in scenario.get("runs", [])]
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


def evaluate_stranger(suites_dir: Path = SUITES_DIR, stranger_dir: Path | None = None) -> list[StrangerResult]:
    """Play every file in the stranger folder and judge it against its flag.

    A file passes or fails as a scenario does. One marked expected_failing that fails is expected failing; one so
    marked that passes is a failure of the suite, because its fix must be recorded by removing the flag in the
    same pull request; one not so marked that fails is a failure. Its id must name an entry in a suite.
    Source: docs/decisions.md, decision 147.
    """
    stranger_dir = suites_dir / "scenarios" / "stranger" if stranger_dir is None else stranger_dir
    ids = {entry["id"] for _, filename in SUITES for entry in load_suite(suites_dir / filename)}
    results = []
    for path in sorted(stranger_dir.glob("*.yaml")) if stranger_dir.is_dir() else []:
        scenario = load_suite(path)
        flagged = scenario.get("expected_failing") is True
        entry_id = str(scenario.get("id", ""))
        if entry_id in ids:
            runs, note = _run_file(path, entry_id)
        else:
            runs, note = [RunResult([], [f"{entry_id or 'the file'} names no entry in a suite"])], scenario.get("note")
        passed = all(run.passed for run in runs)
        status = {(True, False): PASSED, (True, True): FLAG_TO_REMOVE, (False, True): EXPECTED_FAILING}.get((passed, flagged), FAILED)
        results.append(
            StrangerResult(path.name, entry_id, str(scenario.get("stranger_task", "")), str(scenario.get("stranger_run", "")), flagged, status, runs, note)
        )
    return results


def stranger_failures(results: list[StrangerResult]) -> list[str]:
    """Why the stranger runs fail the suite, one line per file: a flagged file that passes, or a file that fails
    without the flag."""
    lines = []
    for result in results:
        if result.status == FLAG_TO_REMOVE:
            lines.append(f"{result.file} passes but is marked expected_failing: remove the flag in the pull request that fixed it.")
        elif result.status == FAILED:
            reasons = "; ".join(failure for run in result.runs for failure in run.failures)
            lines.append(f"{result.file} fails: {reasons}")
    return lines


class ModelCallTimeout(ModelAdapterError):
    """A live call that gave no answer within the run's time limit."""


class LiveRefused(Exception):
    """A live run that did not start, with the reason in plain words for the person who ran it."""


@dataclass
class LiveProvider:
    """The provider a live run calls, and what that run counted.

    `settings` is the environment as the API reads it. The run builds every adapter from it with the named
    provider as `MODEL_PROVIDER`, so naming the fallback provider makes it the primary for the run, and the
    fallback setting stays as it is. `build` is `ProviderModelAdapter` except in tests, which pass a fake.
    """

    name: str
    settings: Mapping[str, str]
    build: Callable[[Mapping[str, str]], ModelAdapter] = ProviderModelAdapter
    call_timeout: float = LIVE_CALL_TIMEOUT_SECONDS
    loop_calls: int = 0
    council_calls: int = 0
    # Which provider answered each call, read from the message, so a fallback that answered shows in the report.
    answered_by: Counter = field(default_factory=Counter)

    @property
    def env(self) -> dict[str, str]:
        return {**self.settings, "MODEL_PROVIDER": self.name}

    def adapter(self, council: bool) -> "_Recording":
        """A fresh adapter for one run's loop, or for its council over the council model variables."""
        return _Recording(self.build(council_env(self.env) if council else self.env), self, council)


class _Recording(ModelAdapter):
    """Passes each call to the provider's adapter, keeping what the model received and counting the call."""

    def __init__(self, inner: ModelAdapter, live: LiveProvider, council: bool) -> None:
        self._inner, self._live, self._council = inner, live, council
        self.calls: list[tuple[list[Message], list[dict[str, Any]]]] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        self.calls.append((list(messages), list(tools)))
        if self._council:
            self._live.council_calls += 1
        else:
            self._live.loop_calls += 1
        message = self._within_time_limit(messages, tools)
        self._live.answered_by[message.provider or "unnamed"] += 1
        return message

    def _within_time_limit(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        """The provider's answer, or ModelCallTimeout once the limit passes with none.

        The call runs on a daemon thread, which a timed out call is left on, so neither the rest of the run
        nor the end of the process waits for it.
        """
        outcome: dict[str, Any] = {}

        def call() -> None:
            try:
                outcome["message"] = self._inner.complete(messages, tools)
            except BaseException as error:  # anti-pattern: SILENT-EXCEPT ok, the error is raised again on the calling thread below
                outcome["error"] = error

        worker = threading.Thread(target=call, daemon=True)
        worker.start()
        worker.join(self._live.call_timeout)
        if worker.is_alive():
            raise ModelCallTimeout(
                f"{self._live.name} gave no answer within {self._live.call_timeout:g} seconds", provider=self._live.name
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome["message"]


def resolve_provider(name: str, env: Mapping[str, str]) -> str:
    """A provider by its own name, or primary and fallback read from MODEL_PROVIDER and FALLBACK_MODEL_PROVIDER."""
    if name == "primary":
        name = env.get("MODEL_PROVIDER") or DEFAULT_PROVIDER
    elif name == "fallback":
        name = env.get("FALLBACK_MODEL_PROVIDER") or DEFAULT_FALLBACK_PROVIDER
    if name not in PROVIDERS:
        raise LiveRefused(f"{name!r} is not a model provider Lifeline can call; the providers are {', '.join(PROVIDERS)}.")
    return name


def require_key(provider: str, env: Mapping[str, str]) -> None:
    variable = api_key_variable(provider)
    if not env.get(variable, "").strip():
        raise LiveRefused(
            f"{variable} is not set, so the live run against {provider} did not start. "
            "Set it in .env, or in the repository secrets for the evidence swap workflow."
        )


def live_limit(env: Mapping[str, str]) -> int | None:
    """How many scenarios marked live a run plays, or None for all of them."""
    value = env.get(LIVE_LIMIT_VARIABLE, "").strip().casefold()
    if value in LIVE_LIMIT_ALL:
        return None
    if not value.isdigit() or int(value) < 1:
        raise LiveRefused(f"{LIVE_LIMIT_VARIABLE} must be empty, all, or a whole number above zero, not {value!r}.")
    return int(value)


def swap_providers(env: Mapping[str, str]) -> tuple[str, str]:
    primary, fallback = resolve_provider("primary", env), resolve_provider("fallback", env)
    if primary == fallback:
        raise LiveRefused(f"MODEL_PROVIDER and FALLBACK_MODEL_PROVIDER both name {primary}, and a swap needs two providers.")
    return primary, fallback


def _live_entries(suites_dir: Path, scenarios_dir: Path, live_dir: Path) -> list[tuple[EntryResult, Path]]:
    """Every scenario marked live, in suite order, then every file in the live only directory."""
    chosen = []
    for suite, filename in SUITES:
        for entry in load_suite(suites_dir / filename):
            path = scenarios_dir / f"{entry['id']}.yaml"
            if path.exists() and load_suite(path).get("live") is True:
                chosen.append((EntryResult(suite, entry["id"], entry["title"], entry.get("tier"), list(entry.get("langs", [])), NOT_AUTOMATED), path))
    for path in sorted(live_dir.glob("*.yaml")) if live_dir.is_dir() else []:
        scenario = load_suite(path)
        if scenario.get("live") is True:
            langs = list(dict.fromkeys(run["lang"] for run in scenario.get("runs", [])))
            chosen.append((EntryResult(LIVE_SUITE, scenario["id"], scenario.get("title", scenario["id"]), None, langs, NOT_AUTOMATED), path))
    return chosen


def evaluate_live(
    live: LiveProvider,
    suites_dir: Path = SUITES_DIR,
    scenarios_dir: Path | None = None,
    live_dir: Path | None = None,
    limit: int | None = None,
) -> list[EntryResult]:
    """Play every scenario marked `live: true` against the live provider, up to `limit` scenarios."""
    scenarios_dir = suites_dir / "scenarios" if scenarios_dir is None else scenarios_dir
    live_dir = suites_dir / "live" if live_dir is None else live_dir
    results = []
    for result, path in _live_entries(suites_dir, scenarios_dir, live_dir)[:limit]:
        result.runs, result.note = _run_file(path, result.id, live)
        statuses = {run.status for run in result.runs}
        result.status = FAILED if FAILED in statuses else PASSED if PASSED in statuses else SKIPPED
        results.append(result)
    return results


def _percent(rate: Fraction) -> str:
    return f"{(Decimal(rate.numerator) * 100 / Decimal(rate.denominator)).quantize(Decimal('0.1'), ROUND_HALF_UP)}"


def _rate(runs: Sequence[RunResult]) -> Fraction:
    """Passed runs over every run. A skipped run is in the count and never among the passed."""
    return Fraction(sum(run.status == PASSED for run in runs), len(runs)) if runs else Fraction(0)


def _redacted(text: str, secrets: Sequence[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTION_MARKER)
    return text


def _secrets(env: Mapping[str, str]) -> list[str]:
    return [env[api_key_variable(name)].strip() for name in PROVIDERS if env.get(api_key_variable(name), "").strip()]


def _quoted(text: str) -> list[str]:
    return [f"    > {line}" if line else "    >" for line in (text.splitlines() or [""])]


def render_live_report(
    results: list[EntryResult], live: LiveProvider, commit: str, generated_at: datetime, seconds: float, limit: int | None
) -> str:
    """The live report for one provider. Every line passes through the key redaction before it is returned."""
    runs = [run for result in results for run in result.runs]
    counts = Counter(run.status for run in runs)
    answered = ", ".join(f"{name} {count}" for name, count in sorted(live.answered_by.items())) or "none"
    lines = [
        f"# Lifeline live evidence report, {live.name}",
        "",
        f"Generated by `core/harness.py --live` at {generated_at.isoformat(timespec='seconds')} from commit `{commit}`.",
        f"The model is {model_name(live.name, live.env)} on {live.name}, the primary for this run. The scripted replies were not used. "
        "Only what the code produces was checked; a text only the script could have written was skipped and is never counted as passed.",
        "",
        f"LIVE_SCENARIO_LIMIT: {limit if limit is not None else 'all'}.",
        f"Scenarios: {len(results)}. Runs: {len(runs)}, {counts[PASSED]} passed, {counts[FAILED]} failed, {counts[SKIPPED]} skipped.",
        f"Pass rate: {counts[PASSED]} of {len(runs)} runs, {_percent(_rate(runs))}%.",
        f"Model calls: {live.loop_calls + live.council_calls}, of which the council made {live.council_calls}. Answered by: {answered}.",
        f"Wall clock: {Decimal(str(seconds)).quantize(Decimal('0.1'), ROUND_HALF_UP)} seconds.",
        "",
        "## By language, runs",
        "",
        _row("Language", "Runs", "Passed", "Failed", "Skipped"),
        _row(*["---"] * 5),
    ]
    for lang in sorted({lang for run in runs for lang in run.langs}):
        chosen = Counter(run.status for run in runs if lang in run.langs)
        lines.append(_row(lang, sum(chosen.values()), chosen[PASSED], chosen[FAILED], chosen[SKIPPED]))
    lines += [
        "",
        "## Runs",
        "",
        "Reads stripped counts the allowed T0 triples, a proposal, its decision and its execution, set aside before "
        "the ledger kinds were compared, because a live model may read before it acts.",
        "",
        _row("Id", "Suite", "Title", "Languages", "Result", "Checks skipped", "Reads stripped"),
        _row(*["---"] * 7),
    ]
    for result in results:
        for run in result.runs:
            lines.append(_row(result.id, result.suite, result.title, ", ".join(run.langs), run.status, len(run.skipped), run.stripped))
    failed = [(result, number, run) for result in results for number, run in enumerate(result.runs, start=1) if run.status == FAILED]
    if failed:
        lines += ["", "## Failures", "", "Each failure keeps every reply of its run as the student saw it, after the reply guard.", ""]
        for result, number, run in failed:
            lines.append(f"1. {result.id}, run {number}, in {', '.join(run.langs) or 'no language'}:")
            lines += [f"    1. {failure}" for failure in run.failures]
            for turn, reply in enumerate(run.replies, start=1):
                lines.append(f"    Reply {turn}:")
                lines += _quoted(reply)
    skipped = [(result, number, run) for result in results for number, run in enumerate(result.runs, start=1) if run.skipped]
    if skipped:
        lines += ["", "## Skipped checks", ""]
        for result, number, run in skipped:
            lines += [f"1. {result.id}, run {number}: {text}" for text in run.skipped]
    notes = [result for result in results if result.note]
    if notes:
        lines += ["", "## Notes", "", _row("Id", "Note"), _row("---", "---")]
        lines += [_row(result.id, " ".join(result.note.split())) for result in notes]
    return _redacted("\n".join(lines) + "\n", _secrets(live.env))


@dataclass
class SwapSummary:
    primary_runs: int
    primary_counts: Counter
    fallback_runs: int
    fallback_counts: Counter
    primary_rate: Fraction
    fallback_rate: Fraction
    # Each run whose result differs: the entry id, the run's number, its languages, then each provider's result.
    disagreements: list[tuple[str, int, list[str], str, str]]

    @property
    def difference(self) -> Fraction:
        return self.primary_rate - self.fallback_rate


def swap_summary(primary: list[EntryResult], fallback: list[EntryResult]) -> SwapSummary:
    """Both providers' pass rates and every run where their results differ, matched by entry and run number."""

    def by_run(results: list[EntryResult]) -> dict[tuple[str, int], RunResult]:
        return {(result.id, number): run for result in results for number, run in enumerate(result.runs, start=1)}

    ours, theirs = by_run(primary), by_run(fallback)
    disagreements = [
        (entry_id, number, run.langs, run.status, theirs[(entry_id, number)].status if (entry_id, number) in theirs else "not run")
        for (entry_id, number), run in ours.items()
        if (entry_id, number) not in theirs or theirs[(entry_id, number)].status != run.status
    ]
    disagreements += [
        (entry_id, number, run.langs, "not run", run.status) for (entry_id, number), run in theirs.items() if (entry_id, number) not in ours
    ]
    return SwapSummary(
        len(ours),
        Counter(run.status for run in ours.values()),
        len(theirs),
        Counter(run.status for run in theirs.values()),
        _rate(list(ours.values())),
        _rate(list(theirs.values())),
        disagreements,
    )


def render_swap_report(summary: SwapSummary, primary: str, fallback: str, commit: str, generated_at: datetime) -> str:
    lines = [
        "# Lifeline provider swap report",
        "",
        f"Generated by `core/harness.py --swap` at {generated_at.isoformat(timespec='seconds')} from commit `{commit}`.",
        f"Each provider played the same scenarios marked live as the primary of its own run. The full runs are in "
        f"`evidence/report-{primary}.md` and `evidence/report-{fallback}.md`.",
        "",
        _row("Provider", "Role", "Runs", "Passed", "Failed", "Skipped", "Pass rate"),
        _row(*["---"] * 7),
    ]
    for name, role, runs, counts, rate in (
        (primary, "primary", summary.primary_runs, summary.primary_counts, summary.primary_rate),
        (fallback, "fallback", summary.fallback_runs, summary.fallback_counts, summary.fallback_rate),
    ):
        lines.append(_row(name, role, runs, counts[PASSED], counts[FAILED], counts[SKIPPED], f"{_percent(rate)}%"))
    lines += ["", f"Difference, {primary} minus {fallback}: {_percent(summary.difference)} percentage points.", "", "## Disagreements", ""]
    if summary.disagreements:
        lines += [_row("Id", "Run", "Languages", primary, fallback), _row(*["---"] * 5)]
        lines += [_row(entry_id, number, ", ".join(langs), ours, theirs) for entry_id, number, langs, ours, theirs in summary.disagreements]
    else:
        lines.append("The two providers agreed on every run.")
    return "\n".join(lines) + "\n"


def _live_report_path(provider: str) -> Path:
    return ROOT / "evidence" / f"report-{provider}.md"


def _play_live(provider: str, env: Mapping[str, str], limit: int | None) -> list[EntryResult]:
    live = LiveProvider(provider, env)
    started = time.monotonic()
    results = evaluate_live(live, limit=limit)
    seconds = time.monotonic() - started
    path = _live_report_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_live_report(results, live, _commit(), datetime.now(timezone.utc), seconds, limit), encoding="utf-8")
    runs = [run for result in results for run in result.runs]
    counts = Counter(run.status for run in runs)
    print(
        f"{path.relative_to(ROOT)}: {counts[PASSED]} passed, {counts[FAILED]} failed, {counts[SKIPPED]} skipped "
        f"of {len(runs)} runs, {live.loop_calls + live.council_calls} model calls"
    )
    return results


def main_live(provider: str | None, swap: bool) -> int:
    """A live run, which only an explicit argument starts. A live failure is evidence, not a broken build, so the
    exit is 0 once the run has started and 2 when it refuses."""
    env = environment(None)
    try:
        limit = live_limit(env)
        providers = swap_providers(env) if swap else (resolve_provider(provider or "", env),)
        for name in providers:
            require_key(name, env)
    except LiveRefused as refused:
        print(refused, file=sys.stderr)
        return 2
    results = [_play_live(name, env, limit) for name in providers]
    if swap:
        summary = swap_summary(*results)
        SWAP_REPORT_PATH.write_text(render_swap_report(summary, *providers, _commit(), datetime.now(timezone.utc)), encoding="utf-8")
        print(
            f"{SWAP_REPORT_PATH.relative_to(ROOT)}: {providers[0]} {_percent(summary.primary_rate)}%, "
            f"{providers[1]} {_percent(summary.fallback_rate)}%, {len(summary.disagreements)} disagreements"
        )
    return 0


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def _count_table(title: str, key: str, groups: dict[str, list[EntryResult]]) -> list[str]:
    lines = [f"## {title}", "", _row(key, "Entries", "Passed", "Failed", "Not automated"), _row(*["---"] * 5)]
    for name, entries in groups.items():
        counts = Counter(entry.status for entry in entries)
        lines.append(_row(name, len(entries), counts[PASSED], counts[FAILED], counts[NOT_AUTOMATED]))
    return lines + [""]


def render_report(
    results: list[EntryResult], commit: str, generated_at: datetime, stranger: list[StrangerResult] | None = None
) -> str:
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
    if stranger is not None:
        lines += _stranger_section(stranger)
    return "\n".join(lines) + "\n"


def _stranger_section(stranger: list[StrangerResult]) -> list[str]:
    """The stranger runs, apart from the suite entries above, so those counts keep their meaning."""
    counts = Counter(result.status for result in stranger)
    lines = [
        "",
        "## Stranger runs",
        "",
        "Every file in `suites/scenarios/stranger`, from the stranger tests in `docs/stranger_test.md`, played apart from "
        "the suite entries above. A file marked expected failing records a failure not yet fixed; one that passes "
        "while so marked fails the suite until the flag is removed.",
        "",
        _row("Files", "Passed", "Expected failing", "Failed", "Passes but flagged"),
        _row(*["---"] * 5),
        _row(len(stranger), counts[PASSED], counts[EXPECTED_FAILING], counts[FAILED], counts[FLAG_TO_REMOVE]),
        "",
        _row("File", "Entry", "Task", "Run", "Result", "Note"),
        _row(*["---"] * 6),
    ]
    lines += [_row(r.file, r.id, r.task, r.run, r.status, r.note or "") for r in stranger]
    failures = stranger_failures(stranger)
    if failures:
        lines += ["", "### Stranger failures", "", *(f"1. {line}" for line in failures)]
    return lines


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.harness", description="Play the scenarios and write the evidence report.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", metavar="PROVIDER", help="play the scenarios marked live against a real provider: anthropic, dashscope, primary or fallback")
    mode.add_argument("--swap", action="store_true", help="play them live against the primary and the fallback provider and compare")
    arguments = parser.parse_args(argv)
    if arguments.live is not None or arguments.swap:
        return main_live(arguments.live, arguments.swap)
    results = evaluate()
    stranger = evaluate_stranger()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results, _commit(), datetime.now(timezone.utc), stranger), encoding="utf-8")
    counts = Counter(result.status for result in results)
    strange = Counter(result.status for result in stranger)
    print(
        f"{REPORT_PATH.relative_to(ROOT)}: {counts[PASSED]} passed, {counts[FAILED]} failed, "
        f"{counts[NOT_AUTOMATED]} not automated; stranger runs: {strange[PASSED]} passed, "
        f"{strange[EXPECTED_FAILING]} expected failing, {strange[FAILED]} failed, {strange[FLAG_TO_REMOVE]} passes but flagged"
    )
    for line in stranger_failures(stranger):
        print(line)
    return 1 if counts[FAILED] or stranger_failures(stranger) else 0


if __name__ == "__main__":
    sys.exit(main())
