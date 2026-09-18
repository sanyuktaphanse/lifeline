from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from contracts.interfaces import ModelAdapter
from contracts.schemas import (
    AgentReply,
    Decision,
    LedgerEntry,
    Mandate,
    Message,
    PrecheckResult,
    Role,
    TraceResult,
)
from core.agent import AgentLoop
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from core.model_adapter import ModelAdapterError, ProviderModelAdapter
from rails.fake_rail import FakeRail
from rails.fake_router import FakeRouter

DEMO_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "demo_user.yaml"
# Source: this module. The Next.js app runs on localhost; any port is allowed, no other host is.
LOCAL_ORIGINS = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
# Source: this module. A guard against oversized requests to the model, not a money rule.
MAX_TEXT_CHARS = 4000


class ChatRequest(BaseModel):
    user_id: str
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    lang: str | None = None


class ConfirmRequest(BaseModel):
    user_id: str
    confirmation_token: str
    lang: str | None = None


class TraceRequest(BaseModel):
    user_id: str
    receipt_id: str


class PrecheckRequest(BaseModel):
    user_id: str
    action_kind: str
    provider: str


class VerifyResult(BaseModel):
    first_broken_seq: int | None


class Health(BaseModel):
    status: str


def demo_rails(traces: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, FakeRail]:
    now = datetime.now(timezone.utc)
    scripted = {
        rail: {
            trace["receipt_id"]: TraceResult.model_validate({"stage_entered_at": now, **trace})
            for trace in rail_traces
        }
        for rail, rail_traces in (traces or {}).items()
    }
    return {
        "wise": FakeRail(scripted.get("wise"), name="wise", simulated=False),
        "bank_wire": FakeRail(scripted.get("bank_wire"), name="bank_wire", simulated=False),
        "sim_pix": FakeRail(scripted.get("sim_pix"), name="sim_pix", simulated=True),
        "revolut": FakeRail(scripted.get("revolut"), name="revolut", simulated=False),
    }


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _demo_mandate(fixture: dict[str, Any]) -> Mandate:
    now = datetime.now(timezone.utc)
    return Mandate.model_validate(
        {
            "user_id": fixture["user_id"],
            "valid_from": now,
            "valid_until": now + timedelta(days=fixture["valid_days"]),
            **fixture["mandate"],
        }
    )


def _without_tokens(reply: AgentReply, keep_confirmation_token: bool) -> AgentReply:
    update: dict[str, Any] = {}
    if reply.decision is not None:
        update["decision"] = reply.decision.model_copy(update={"confirmation_token": None})
    if reply.confirmation is not None:
        confirmation = reply.confirmation.model_copy(
            update={"action": reply.confirmation.action.model_copy(update={"confirmation_token": None})}
        )
        if not keep_confirmation_token:
            confirmation = confirmation.model_copy(update={"confirmation_token": ""})
        update["confirmation"] = confirmation
    return reply.model_copy(update=update)


def create_app(
    adapter: ModelAdapter | None = None,
    fixture_path: Path = DEMO_FIXTURE,
    rails: dict[str, FakeRail] | None = None,
) -> FastAPI:
    fixture = _load_fixture(fixture_path)
    user_id = fixture["user_id"]
    ledger = HashChainLedger()
    loop = AgentLoop(
        adapter=adapter if adapter is not None else ProviderModelAdapter(),
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails=rails if rails is not None else demo_rails(fixture.get("traces")),
        mandates={user_id: _demo_mandate(fixture)},
        balances={user_id: {currency: Decimal(amount) for currency, amount in fixture["balances"].items()}},
        pending={},
    )
    users = {user_id}

    app = FastAPI(title="Lifeline API")
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

    def known(user: str) -> str:
        if user not in users:
            raise HTTPException(status_code=404, detail=f"No user {user}.")
        return user

    def direct(user: str, tool: str, arguments: dict[str, Any], key: str) -> dict[str, Any]:
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
        return _without_tokens(loop.handle(known(request.user_id), message), keep_confirmation_token=True)

    @app.post("/confirm")
    def confirm(request: ConfirmRequest) -> AgentReply:
        fields = {"lang": request.lang} if request.lang else {}
        message = Message(role=Role.USER, text="", **fields)
        reply = loop.handle(known(request.user_id), message, confirmation_token=request.confirmation_token)
        return _without_tokens(reply, keep_confirmation_token=False)

    @app.get("/ledger/{user}")
    def entries(user: str) -> list[LedgerEntry]:
        known(user)
        return [entry for entry in ledger.entries() if entry.payload.get("user_id") == user]

    @app.get("/ledger/{user}/verify")
    def verify(user: str) -> VerifyResult:
        known(user)
        return VerifyResult(first_broken_seq=ledger.verify())

    @app.post("/trace")
    def trace(request: TraceRequest) -> TraceResult:
        result = direct(request.user_id, "trace_transfer", {"receipt_id": request.receipt_id}, "trace")
        return TraceResult.model_validate(result)

    @app.post("/precheck")
    def precheck(request: PrecheckRequest) -> PrecheckResult:
        arguments = {"action_kind": request.action_kind, "provider": request.provider}
        return PrecheckResult.model_validate(direct(request.user_id, "precheck", arguments, "precheck"))

    return app
