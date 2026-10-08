import asyncio
import logging
import os
import threading
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, Field

from contracts.interfaces import Anchor, Council, Ledger, ModelAdapter
from contracts.schemas import (
    AgentReply,
    Decision,
    LanguageCode,
    LedgerEntry,
    Mandate,
    Message,
    Plan,
    PrecheckResult,
    Receipt,
    RescueReply,
    RescueTrigger,
    Role,
    Route,
    Source,
    StandingEvent,
    TraceResult,
)
from core.agent import AgentLoop
from core.anchor_local import anchor_for
from core.conversation_store import ConversationStore
from core.council import FiveVoiceCouncil
from core.ledger import JsonlLedger
from core.mandate import DeterministicMandateEngine
from core.monthly import is_month, render
from core.model_adapter import ModelAdapterError, ProviderModelAdapter, council_adapter, environment
from rails.fake_rail import FakeRail, scripted_traces
from rails.inbound import inbound_from_fixture, seed_inbound
from rails.sim.cn_bank_remit import CnBankRemitSimRail
from rails.sim.pix import PixSimRail
from rails.sim.upi_paynow import UpiPayNowSimRail
from rails.fake_router import FakeRouter

ROOT = Path(__file__).resolve().parent.parent
DEMO_FIXTURE = ROOT / "fixtures" / "demo_user.yaml"
# A parent in India, loaded beside the demo student when the file exists, so the app can show both sides.
DEMO_PARENT = ROOT / "fixtures" / "demo_parent.yaml"
LEDGER_PATH = ROOT / "data" / "ledger.jsonl"
CONVERSATIONS_PATH = ROOT / "data" / "conversations.jsonl"
# The anchors are kept beside the ledger they anchor, so data/anchors.jsonl for data/ledger.jsonl.
ANCHORS_FILE = "anchors.jsonl"
# Source: this module. The Next.js app runs on localhost; any port is allowed, no other host is.
LOCAL_ORIGINS = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
# Source: this module. A guard against oversized requests to the model, not a money rule.
MAX_TEXT_CHARS = 4000
# Source: this module. Pasted messages and documents run longer than typed text; attack X18 uses a long one.
MAX_PASTED_CHARS = 20000
# Source: docs/decisions.md, 18 September 2026. The scheduler checks for due standing runs once a minute.
TICK_SECONDS = 60.0

# Source: .env.example. The council costs five model calls per escalated transfer, so it is off
# unless COUNCIL names one of these values.
COUNCIL_ON = frozenset({"on", "true", "1", "yes"})
# Source: .env.example. The simulated rails beyond Pix are on unless SIM_RAILS names one of these.
SIM_RAILS_OFF = frozenset({"off", "false", "0", "no"})

logger = logging.getLogger("lifeline.api")


class ChatRequest(BaseModel):
    user_id: str
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    pasted_text: str | None = Field(default=None, min_length=1, max_length=MAX_PASTED_CHARS)
    # A language reaches the model inside the system prompt, so a caller may name only a code
    # Lifeline replies in. Source: LANGUAGES in contracts/schemas.py.
    lang: LanguageCode | None = None


class ConfirmRequest(BaseModel):
    user_id: str
    confirmation_token: str
    lang: LanguageCode | None = None


class RescueStartRequest(BaseModel):
    user_id: str
    trigger: RescueTrigger
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    lang: LanguageCode | None = None


class RescueStepRequest(BaseModel):
    user_id: str
    # Empty when the step only confirms, or when the student continues without the allowance.
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    confirmation_token: str | None = None
    lang: LanguageCode | None = None


class TraceRequest(BaseModel):
    user_id: str
    receipt_id: str


class PrecheckRequest(BaseModel):
    user_id: str
    action_kind: str
    provider: str
    # What the chat tool carries, so the app can run the document request flag and the structuring
    # check without the model. The loop writes both as fixed kinds and roles before anything is written,
    # so a raw address or a name sent here never reaches the ledger. Source: docs/decisions.md, 8 October 2026.
    channel: str | None = Field(default=None, min_length=1, max_length=MAX_TEXT_CHARS)
    senders: list[str] | str | None = Field(default=None, max_length=MAX_TEXT_CHARS)


class RunDueRequest(BaseModel):
    now: AwareDatetime


class VerifyResult(BaseModel):
    first_broken_seq: int | None
    # AgentLoop.anchor_status: anchored false and the kind when there is no anchor, else the latest
    # anchored head, its sequence, whether the anchor store verifies it, its time, and the kind.
    anchor: dict[str, Any]


class Health(BaseModel):
    status: str


class MonthlyNote(BaseModel):
    """The monthly note for the app: the text, the figures it was built from, and every entry behind them."""

    user_id: str
    month: str
    lang: str
    text: str
    summary: dict[str, Any]
    seqs: list[int]


def demo_rails(
    traces: dict[str, list[dict[str, Any]]] | None = None,
    sim_rails: bool = True,
    pix_key_on_file: list[str] | None = None,
    documents_on_file: list[str] | None = None,
    quota_position_known: bool = False,
) -> dict[str, Any]:
    scripted = scripted_traces(traces)
    rails: dict[str, Any] = {
        "wise": FakeRail(scripted.get("wise"), name="wise", simulated=False),
        "bank_wire": FakeRail(scripted.get("bank_wire"), name="bank_wire", simulated=False),
        "sim_pix": PixSimRail(pix_key_on_file=pix_key_on_file or ()),
        "revolut": FakeRail(scripted.get("revolut"), name="revolut", simulated=False),
    }
    if sim_rails:
        # The API always runs the normal script; a scenario chooses others through the harness.
        rails["upi_paynow_sim"] = UpiPayNowSimRail()
        rails["cn_bank_remit_sim"] = CnBankRemitSimRail(
            documents_on_file=documents_on_file or (), quota_position_known=quota_position_known
        )
    return rails


def sim_rails_on(env: Mapping[str, str] | None = None) -> bool:
    """Whether the API registers the simulated rails beyond Pix: on unless SIM_RAILS turns them off."""
    return environment(env).get("SIM_RAILS", "").strip().casefold() not in SIM_RAILS_OFF


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _demo_mandate(fixture: dict[str, Any], ledger: Ledger) -> Mandate:
    entries = ledger.entries()
    began = entries[0].ts if entries else datetime.now(timezone.utc)
    start = began.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return Mandate.model_validate(
        {
            "user_id": fixture["user_id"],
            "valid_from": start,
            "valid_until": start + timedelta(days=fixture["valid_days"]),
            **fixture["mandate"],
        }
    )


def _restore_rails(rails: dict[str, FakeRail], ledger: Ledger) -> None:
    paid: dict[str, dict[str, Any]] = {}
    for entry in ledger.entries():
        if entry.kind == "execution" and "route" in entry.payload:
            paid[entry.payload["idempotency_key"]] = entry.payload
        elif entry.kind == "receipt" and entry.payload.get("rail") in rails:
            receipt = Receipt.model_validate(entry.payload["receipt"])
            execution = paid[receipt.idempotency_key]
            route = Route.model_validate(execution["route"])
            rails[entry.payload["rail"]].restore(receipt, route, execution["mandate_ref"])
        elif (
            entry.kind == "note"
            and entry.payload.get("kind") == "cancel_result"
            and entry.payload.get("status") == "done"
            and entry.payload.get("rail") in rails
        ):
            # A cancel the rail carried out stays carried out after a restart.
            rails[entry.payload["rail"]].mark_cancelled(entry.payload["receipt_id"])


def _without_tokens[R: AgentReply](reply: R) -> R:
    update: dict[str, Any] = {}
    if reply.decision is not None:
        update["decision"] = reply.decision.model_copy(update={"confirmation_token": None})
    if reply.confirmation is not None:
        update["confirmation"] = reply.confirmation.model_copy(
            update={"action": reply.confirmation.action.model_copy(update={"confirmation_token": None})}
        )
    return reply.model_copy(update=update)


def _event_without_tokens(event: StandingEvent) -> StandingEvent:
    if event.decision is None:
        return event
    return event.model_copy(update={"decision": event.decision.model_copy(update={"confirmation_token": None})})


def council_for(env: Mapping[str, str] | None = None) -> FiveVoiceCouncil | None:
    """The council this process runs with, or nothing when `COUNCIL` does not turn it on.

    The council calls the model through its own adapter, built over the council model variables,
    so its calls are never counted against the agent loop's cap for a turn.
    """
    env = environment(env)
    if env.get("COUNCIL", "").strip().casefold() not in COUNCIL_ON:
        return None
    return FiveVoiceCouncil(council_adapter(env))


def create_app(
    adapter: ModelAdapter | None = None,
    fixture_path: Path = DEMO_FIXTURE,
    rails: dict[str, FakeRail] | None = None,
    ledger_path: Path | None = None,
    conversations_path: Path | None = None,
    tick_seconds: float | None = TICK_SECONDS,
    council: Council | None = None,
    sim_rails: bool | None = None,
    anchor: Anchor | None = None,
    parent_fixture_path: Path | None = DEMO_PARENT,
) -> FastAPI:
    fixture = _load_fixture(fixture_path)
    parent = _load_fixture(parent_fixture_path) if parent_fixture_path is not None and parent_fixture_path.exists() else None
    user_id = fixture["user_id"]
    ledger_path = ledger_path or LEDGER_PATH
    ledger = JsonlLedger(ledger_path)
    if anchor is None:
        anchor = anchor_for(None, ledger_path.parent / ANCHORS_FILE)
    if rails is None:
        rails = demo_rails(
            fixture.get("traces"),
            sim_rails_on() if sim_rails is None else sim_rails,
            fixture.get("pix_key_on_file"),
            fixture.get("documents_on_file"),
            bool(fixture.get("quota_position_known")),
        )
    # A fixture's inbound receipts on a rail this process does not build are left out, not an error.
    fixture = {**fixture, "inbound_receipts": {
        key: transfers for key, transfers in (fixture.get("inbound_receipts") or {}).items() if key in rails
    }}
    _restore_rails(rails, ledger)
    # The demo student first, then the parent when its fixture exists.
    people = [fixture, *([parent] if parent is not None else [])]
    # A parent's transfer to the student is seeded on every start from the fixture, never from the ledger.
    inbound = seed_inbound(rails, inbound_from_fixture(fixture.get("inbound_receipts"), rails))
    loop = AgentLoop(
        adapter=adapter if adapter is not None else ProviderModelAdapter(),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=rails,
        mandates={person["user_id"]: _demo_mandate(person, ledger) for person in people},
        balances={
            person["user_id"]: {currency: Decimal(amount) for currency, amount in person["balances"].items()}
            for person in people
        },
        pending={},
        conversations=ConversationStore(conversations_path or CONVERSATIONS_PATH),
        council=council if council is not None else council_for(),
        plans={person["user_id"]: Plan.model_validate(person["plan"]) for person in people},
        inbound_receipts={user_id: inbound},
        anchor=anchor,
        chinese_cards={user_id: fixture.get("chinese_cards") or []},
    )
    users = {person["user_id"] for person in people}
    # Requests run in worker threads and the tick on the event loop; the agent loop is not thread safe.
    lock = threading.Lock()

    def run_due(now: datetime) -> list[StandingEvent]:
        with lock:
            events = [_event_without_tokens(event) for event in loop.run_due_standing_mandates(now)]
            # The first tick in a new month writes each student's note for the month that ended, once.
            loop.write_monthly_notes(now)
            return events

    async def tick() -> None:
        while True:
            await asyncio.sleep(tick_seconds)
            try:
                events = await asyncio.to_thread(run_due, datetime.now(timezone.utc))
            except Exception:  # anti-pattern: SILENT-EXCEPT ok, logged with its traceback and the next tick still runs
                logger.exception("standing tick failed")
                continue
            for event in events:
                logger.info(
                    "standing %s user=%s standing=%s period=%s receipt=%s",
                    event.kind,
                    event.user_id,
                    event.standing_mandate_id,
                    event.period,
                    event.receipt.receipt_id if event.receipt else None,
                )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(tick()) if tick_seconds else None
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(title="Lifeline API", lifespan=lifespan)
    app.state.loop = loop
    app.state.ledger = ledger
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ModelAdapterError)
    async def model_unavailable(request: Request, error: ModelAdapterError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        errors = error.errors()
        if request.url.path.startswith("/rescue/"):
            # A rescue request can hold the identity answer, so its 422 never echoes what was sent.
            errors = [{name: value for name, value in item.items() if name != "input"} for item in errors]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    def known(user: str) -> str:
        if user not in users:
            raise HTTPException(status_code=404, detail=f"No user {user}.")
        return user

    def direct(user: str, tool: str, arguments: dict[str, Any], key: str) -> dict[str, Any]:
        with lock:
            decision, result = loop.act(known(user), tool, arguments)
        refused(decision)
        if key not in result:
            raise HTTPException(status_code=404, detail=result.get("error", f"No {key} result."))
        return result[key]

    def refused(decision: Decision | None) -> None:
        if decision is not None and not decision.allowed:
            raise HTTPException(status_code=403, detail={"rule_ids": decision.rule_ids, "reasons": decision.reasons})

    @app.get("/health")
    def health() -> Health:
        return Health(status="ok")

    @app.post("/chat")
    def chat(request: ChatRequest) -> AgentReply:
        fields = {"lang": request.lang} if request.lang else {}
        message = Message(role=Role.USER, text=request.text, **fields)
        pasted = None
        if request.pasted_text is not None:
            pasted = Message(role=Role.USER, text=request.pasted_text, source=Source.PASTED_TEXT)
        with lock:
            reply = loop.handle(known(request.user_id), message, pasted=pasted)
        return _without_tokens(reply)

    @app.post("/confirm")
    def confirm(request: ConfirmRequest) -> AgentReply:
        fields = {"lang": request.lang} if request.lang else {}
        message = Message(role=Role.USER, text="", **fields)
        with lock:
            reply = loop.handle(known(request.user_id), message, confirmation_token=request.confirmation_token)
        return _without_tokens(reply)

    @app.post("/rescue/start")
    def rescue_start(request: RescueStartRequest) -> RescueReply:
        fields = {"lang": request.lang} if request.lang else {}
        message = Message(role=Role.USER, text=request.text, **fields)
        with lock:
            reply = loop.rescue_start(known(request.user_id), request.trigger.value, message)
        return _without_tokens(reply)

    @app.post("/rescue/step")
    def rescue_step(request: RescueStepRequest) -> RescueReply:
        fields = {"lang": request.lang} if request.lang else {}
        message = Message(role=Role.USER, text=request.text, **fields)
        with lock:
            reply = loop.rescue_step(known(request.user_id), message, confirmation_token=request.confirmation_token)
        return _without_tokens(reply)

    @app.get("/ledger/{user}")
    def entries(user: str) -> list[LedgerEntry]:
        known(user)
        with lock:
            return [entry for entry in ledger.entries() if entry.payload.get("user_id") == user]

    @app.get("/ledger/{user}/verify")
    def verify(user: str) -> VerifyResult:
        known(user)
        with lock:
            return VerifyResult(first_broken_seq=ledger.verify(), anchor=loop.anchor_status())

    @app.post("/trace")
    def trace(request: TraceRequest) -> TraceResult:
        result = direct(request.user_id, "trace_transfer", {"receipt_id": request.receipt_id}, "trace")
        return TraceResult.model_validate(result)

    @app.post("/precheck")
    def precheck(request: PrecheckRequest) -> PrecheckResult:
        arguments: dict[str, Any] = {"action_kind": request.action_kind, "provider": request.provider}
        if request.channel is not None:
            arguments["channel"] = request.channel
        if request.senders is not None:
            arguments["senders"] = request.senders
        return PrecheckResult.model_validate(direct(request.user_id, "precheck", arguments, "precheck"))

    @app.get("/note/{user}/monthly")
    def monthly_note(user: str, month: str | None = None) -> MonthlyNote:
        known(user)
        if month is not None and not is_month(month):
            # The month is never echoed, so nothing a caller sends comes back in the error.
            raise HTTPException(status_code=422, detail="month must be a four digit year, a hyphen and a two digit month.")
        with lock:
            chosen = month or loop.latest_month(user)
            # The note runs as the T0 tool monthly_summary, through the engine, so the request leaves a
            # proposal, a decision and an execution; the text is rendered as the tick renders it.
            decision, result = loop.act(user, "monthly_summary", {"month": chosen})
            refused(decision)
            lang = loop.student_lang(user)
        if "summary" not in result:
            raise HTTPException(status_code=422, detail=result.get("error", "No note for that month."))
        summary = result["summary"]
        return MonthlyNote(
            user_id=user, month=chosen, lang=lang, text=render(summary, lang), summary=summary, seqs=result["seqs"]
        )

    @app.post("/standing/run_due")
    def standing_run_due(request: RunDueRequest) -> list[StandingEvent]:
        if os.environ.get("LIFELINE_ENV") == "production":
            raise HTTPException(status_code=403, detail="Running standing mandates at a chosen time is for demos and tests only.")
        return run_due(request.now)

    return app
