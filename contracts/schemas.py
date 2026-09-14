from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Corridor = Annotated[str, Field(pattern=r"^[A-Z]{2}>[A-Z]{2}$")]
PositiveAmount = Annotated[Decimal, Field(gt=0)]
NonNegativeAmount = Annotated[Decimal, Field(ge=0)]
Hours = Annotated[float, Field(ge=0)]


class Source(str, Enum):
    USER_TURN = "user_turn"
    PASTED_TEXT = "pasted_text"
    TOOL_RESULT = "tool_result"
    TRANSLATED_TEXT = "translated_text"
    PROVIDER_STATUS = "provider_status"


class Tier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class ActionType(str, Enum):
    TRANSFER = "transfer"
    READ_BALANCE = "read_balance"
    SET_REMINDER = "set_reminder"
    ADD_PAYEE = "add_payee"
    FREEZE_CARD = "freeze_card"
    CHANGE_LIMIT = "change_limit"
    CHANGE_MANDATE = "change_mandate"
    EXPORT_CREDENTIALS = "export_credentials"
    TRACE_TRANSFER = "trace_transfer"
    PRECHECK = "precheck"


class RouteStatus(str, Enum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"
    SIMULATED = "simulated"


class ReceiptStatus(str, Enum):
    CREATED = "created"
    FUNDED = "funded"
    IN_TRANSIT = "in_transit"
    HELD_FOR_REVIEW = "held_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    RETURNED = "returned"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Action(BaseModel):
    type: ActionType
    source: Source = Source.USER_TURN
    idempotency_key: str = Field(min_length=8)
    requested_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    amount: PositiveAmount | None = None
    currency: CurrencyCode | None = None
    corridor: Corridor | None = None
    payee_id: str | None = None
    purpose: str | None = None
    confirmation_token: str | None = None


class StandingMandate(BaseModel):
    id: str
    payee_id: str
    amount: PositiveAmount
    tolerance_pct: Annotated[Decimal, Field(ge=0, le=100)]
    schedule: str
    corridor: Corridor
    purpose: str
    notice_hours: int = Field(ge=0)
    cancel_window_hours: int = Field(ge=0)
    confirmed_at: AwareDatetime
    confirmation_token: str
    active: bool


class Mandate(BaseModel):
    user_id: str
    currency: CurrencyCode
    per_txn_limit: Decimal
    daily_limit: Decimal
    allowed_payees: set[str]
    allowed_corridors: set[str]
    allowed_purposes: set[str]
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    standing_mandates: list[StandingMandate] = Field(default_factory=list)


class Decision(BaseModel):
    allowed: bool
    reasons: list[str]
    rule_ids: list[str]
    tier: Tier
    requires_confirmation: bool = False
    warning_key: str | None = None
    confirmation_token: str | None = None


class Route(BaseModel):
    rail: str
    corridor: Corridor
    amount: PositiveAmount
    currency_from: CurrencyCode
    currency_to: CurrencyCode
    fee: NonNegativeAmount
    spread_cost: NonNegativeAmount
    tax_lines: list[dict[str, Any]]
    arrival_hours: Hours
    status: RouteStatus
    simulated: bool
    limit_ok: bool
    blocked_reason: str | None = None
    rule_id: str | None = None
    fee_source_url: str | None = None
    rate_source: str | None = None
    quoted_at: AwareDatetime


class Receipt(BaseModel):
    receipt_id: str
    rail: str
    amount: PositiveAmount
    currency: CurrencyCode
    status: ReceiptStatus
    stage_entered_at: AwareDatetime
    mandate_ref: str
    simulated: bool
    executed_at: AwareDatetime


class TraceResult(BaseModel):
    receipt_id: str
    status: ReceiptStatus
    stage_entered_at: AwareDatetime
    typical_duration_hours: Hours
    typical_duration_source: str
    next_steps: list[str]
    warnings: list[str]


class PrecheckResult(BaseModel):
    provider: str
    action_kind: str
    documents_likely: list[str]
    review_triggers: list[str]
    ready: bool | None = None
    rule_ids: list[str]


class LedgerEntry(BaseModel):
    seq: int = Field(ge=1)
    ts: AwareDatetime
    actor: str
    kind: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: Role
    text: str
    lang: str = "en"
    source: Source = Source.USER_TURN
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    provider: str | None = None
    model: str | None = None
    provider_content: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def _tool_messages_answer_one_call_as_data(self) -> "Message":
        if self.role is Role.TOOL:
            if self.source is not Source.TOOL_RESULT:
                raise ValueError("A tool message must carry source tool_result.")
            if not self.tool_call_id:
                raise ValueError(
                    "A tool message must carry the tool_call_id of the call it answers."
                )
        return self


class ConfirmationRequest(BaseModel):
    action: Action
    confirmation_token: str
    warning_key: str
    routes: list[Route]
    expires_in_seconds: int = 300


class AgentReply(BaseModel):
    text: str
    lang: str
    confirmation: ConfirmationRequest | None = None
    decision: Decision | None = None
    receipt: Receipt | None = None
    ledger_seqs: list[int]
    provider: str | None = None
    model: str | None = None
