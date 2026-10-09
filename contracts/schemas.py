from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, model_validator

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
# The languages Lifeline writes replies in. Source: the TEXTS table in core/agent.py, which a
# test in tests/test_council.py pins to this tuple so the two cannot drift.
LANGUAGES = ("en", "pt", "zh")
# What the app needs to show each language: its writing direction and its name in its own script. The app reads
# this from GET /health and never hardcodes it. A fourth language is one entry in LANGUAGES, one here and one
# column in every TEXTS table, and tests/test_i18n.py fails until all three are there.
# Source: docs/decisions.md, 9 October 2026.
LANGUAGE_META: dict[str, dict[str, str]] = {
    "en": {"direction": "ltr", "name": "English"},
    "pt": {"direction": "ltr", "name": "Português"},
    "zh": {"direction": "ltr", "name": "中文"},
}
LanguageCode = Annotated[str, Field(pattern=f"^({'|'.join(LANGUAGES)})$")]
Corridor = Annotated[str, Field(pattern=r"^[A-Z]{2}>[A-Z]{2}$")]
PositiveAmount = Annotated[Decimal, Field(gt=0)]
# Source: docs/decisions.md, 18 September 2026. No student transfer comes near one hundred million.
MAX_ACTION_AMOUNT = Decimal("100000000")
ActionAmount = Annotated[Decimal, Field(gt=0, le=MAX_ACTION_AMOUNT)]
NonNegativeAmount = Annotated[Decimal, Field(ge=0)]
Hours = Annotated[float, Field(ge=0)]


class Source(str, Enum):
    USER_TURN = "user_turn"
    PASTED_TEXT = "pasted_text"
    TOOL_RESULT = "tool_result"
    TRANSLATED_TEXT = "translated_text"
    PROVIDER_STATUS = "provider_status"
    STANDING_MANDATE = "standing_mandate"


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
    GET_QUOTE = "get_quote"
    CREATE_STANDING_MANDATE = "create_standing_mandate"
    CANCEL_STANDING_RUN = "cancel_standing_run"
    DEACTIVATE_STANDING_MANDATE = "deactivate_standing_mandate"
    RESCUE_IDENTITY_CHECK = "rescue_identity_check"
    CHECK_WALLET_TOKEN = "check_wallet_token"
    REROUTE_TO_BACKUP = "reroute_to_backup"
    NOTIFY_FAMILY = "notify_family"
    VERIFY_LEDGER = "verify_ledger"
    UPDATE_PLAN = "update_plan"
    CANCEL_TRANSFER = "cancel_transfer"
    MONTHLY_SUMMARY = "monthly_summary"
    RECORD_CASH_WITHDRAWAL = "record_cash_withdrawal"


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


class FreezeStatus(str, Enum):
    DONE = "done"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


class CancelStatus(str, Enum):
    """The three outcomes of a cancel, the same as a freeze's. Source: docs/decisions.md, 8 October 2026."""

    DONE = "done"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# Source: docs/decisions.md, 18 September 2026. A standing run is due monthly on a day from 1 to 28.
StandingSchedule = Annotated[str, Field(pattern=r"^monthly:([1-9]|1[0-9]|2[0-8])$")]


class StandingTerms(BaseModel):
    schedule: StandingSchedule
    tolerance_pct: Annotated[Decimal, Field(ge=0, le=100)]
    notice_hours: int = Field(ge=0)
    cancel_window_hours: int = Field(ge=0)

    @model_validator(mode="after")
    def _cancel_window_ends_by_the_due_time(self) -> "StandingTerms":
        if self.cancel_window_hours > self.notice_hours:
            raise ValueError("cancel_window_hours may not exceed notice_hours.")
        return self


class Action(BaseModel):
    type: ActionType
    source: Source = Source.USER_TURN
    idempotency_key: str = Field(min_length=8)
    requested_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    amount: ActionAmount | None = None
    currency: CurrencyCode | None = None
    corridor: Corridor | None = None
    payee_id: str | None = None
    purpose: str | None = None
    instrument_id: str | None = None
    standing_mandate_id: str | None = None
    standing_terms: StandingTerms | None = None
    confirmation_token: str | None = None
    # The plan fields an update_plan action would change, by name. The engine refuses any name outside
    # PLAN_UPDATE_FIELDS. Source: docs/decisions.md, 8 October 2026.
    plan_update: dict[str, Any] | None = None
    # A cancel names the receipt, and the loop names the student's own transfer that produced it, by
    # its idempotency key, or None when the student's ledger holds no such receipt. The engine refuses
    # a cancel whose cancel_of is not in the student's history. Source: docs/decisions.md, 8 October 2026.
    receipt_id: str | None = None
    cancel_of: str | None = None
    # The day a recorded overseas cash withdrawal was made, which the cash cap counts against the year and
    # the day. Only record_cash_withdrawal carries it. Source: docs/decisions.md, Stage 9 of 8 October 2026.
    withdrawal_date: date | None = None


# The only fields of the resilience plan that update_plan may change. The identity check, the
# allowance and the emergency payee, corridor and purpose, and the trusted contact are never among
# them. Source: docs/decisions.md, 8 October 2026.
PLAN_UPDATE_FIELDS = ("backup_instrument", "backup_route", "wallet_token_present", "cash_plan")


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
    id: str
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
    payee_added_at: dict[str, AwareDatetime] = Field(default_factory=dict)
    # Source: docs/decisions.md, 18 September 2026. A new payee waits 24 hours by default.
    cooling_hours: int = Field(default=24, ge=0)


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
    # Source: docs/decisions.md, 8 October 2026. A rail must see what it carries: the router names
    # the purpose it quoted for, and the loop stamps the payee on the route it is about to pay.
    purpose: str | None = None
    payee_id: str | None = None


class Receipt(BaseModel):
    receipt_id: str
    rail: str
    amount: PositiveAmount
    currency: CurrencyCode
    status: ReceiptStatus
    stage_entered_at: AwareDatetime
    mandate_ref: str
    idempotency_key: str = Field(min_length=8)
    simulated: bool
    executed_at: AwareDatetime
    standing_mandate_id: str | None = None


class TraceResult(BaseModel):
    receipt_id: str
    status: ReceiptStatus
    stage_entered_at: AwareDatetime
    # None when no entry gives a duration; typical_duration_source then names the entry and says so.
    # Source: docs/decisions.md, 8 October 2026.
    typical_duration_hours: Hours | None = None
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


class FreezeResult(BaseModel):
    status: FreezeStatus
    deep_link: str | None = None
    reason: str | None = None


class CancelResult(BaseModel):
    status: CancelStatus
    deep_link: str | None = None
    reason: str | None = None


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


class CouncilAdvice(BaseModel):
    """What the council advised, for a frontend to show without reading the reply text.

    Source: docs/decisions.md, 22 September 2026. The full deliberation, the voices
    included, goes to the ledger as a `council` entry; this is the advice only.
    """

    chosen: str
    runner_up: str
    reason: str
    disagreement: Annotated[float, Field(ge=0, le=1)]
    triggers: list[str]


class CouncilVoice(BaseModel):
    """One voice as the record keeps it: its answer, or its abstention with the raw text."""

    voice: str
    abstained: bool
    position: str | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    reason: str | None = None
    evidence: list[str] | None = None
    raw: str | None = None


class CouncilDeliberation(CouncilAdvice):
    """A whole deliberation: the advice, the question that was asked, and every voice.

    The agent loop validates what a `Council` returns into this model before it reads it, writes
    it, or shows any of it, so an implementation other than this repository's cannot put a value
    of the wrong type, or a field nobody asked for, into the ledger or into a reply.
    """

    question: str
    voices: list[CouncilVoice]


class ConfirmationRequest(BaseModel):
    action: Action
    confirmation_token: str
    warning_key: str
    routes: list[Route]
    selected_route: Route | None = None
    council: CouncilAdvice | None = None
    expires_in_seconds: int = Field(default=300, gt=0)


class AgentReply(BaseModel):
    text: str
    lang: str
    confirmation: ConfirmationRequest | None = None
    decision: Decision | None = None
    receipt: Receipt | None = None
    freeze: FreezeResult | None = None
    cancel: CancelResult | None = None
    ledger_seqs: list[Annotated[int, Field(ge=1)]]
    provider: str | None = None
    model: str | None = None


class StandingEvent(BaseModel):
    kind: Literal["notice", "run", "skipped", "needs_student", "rail_failed", "held"]
    user_id: str
    standing_mandate_id: str
    period: str
    due_at: AwareDatetime
    amount: PositiveAmount
    currency: CurrencyCode
    payee_id: str
    cancel_until: AwareDatetime | None = None
    decision: Decision | None = None
    receipt: Receipt | None = None


# A card is named as issuer:card, such as wise:card_01, and nothing else: no spaces, no prose.
# Source: docs/decisions.md, 8 October 2026.
INSTRUMENT_ID = r"[a-z0-9_]+:[A-Za-z0-9_]+"


class PlanCard(BaseModel):
    """One card the student listed before departure, by the name they gave it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    instrument_id: str = Field(pattern=f"^{INSTRUMENT_ID}$")


class TrustedContact(BaseModel):
    """Who the student asks for help. A name and a channel only: no phone number, no email."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class IdentityCheck(BaseModel):
    """A question and its answer, set before departure. The answer never prints, never dumps, and
    never appears in a validation error."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    question: str = Field(min_length=1)
    expected_answer: SecretStr = Field(min_length=1)


class Plan(BaseModel):
    """The student's resilience plan, which a rescue reads and never writes.

    Source: docs/decisions.md, 8 October 2026. The emergency allowance is the amount a rescue
    proposes as an ordinary T2 transfer; it is never an authority to pay.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    cards: list[PlanCard] = Field(min_length=1)
    primary_instrument: str | None = None
    backup_instrument: str | None = None
    backup_route: str | None = None
    wallet_token_present: bool
    trusted_contact: TrustedContact
    cash_plan: list[str] = Field(default_factory=list)
    replacement_estimates: dict[str, str] = Field(default_factory=dict)
    emergency_allowance: PositiveAmount
    emergency_payee: str = Field(min_length=1)
    emergency_corridor: Corridor
    emergency_purpose: str = Field(min_length=1)
    family_notice_opt_in: bool
    identity_check: IdentityCheck

    @model_validator(mode="after")
    def _names_only_its_own_cards(self) -> "Plan":
        names = [card.name.strip().casefold() for card in self.cards]
        if len(set(names)) != len(names):
            raise ValueError("Two cards in the plan share a name, ignoring case.")
        listed = {card.instrument_id for card in self.cards}
        for field_name in ("primary_instrument", "backup_instrument"):
            value = getattr(self, field_name)
            if value is not None and value not in listed:
                raise ValueError(f"{field_name} {value} is not one of the plan's cards.")
        if self.backup_instrument is not None and self.backup_instrument == self.primary_instrument:
            raise ValueError("The backup instrument cannot be the primary instrument.")
        return self


class RescueState(str, Enum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    S7 = "S7"
    S8 = "S8"
    S9 = "S9"
    DONE = "done"


class RescueTrigger(str, Enum):
    CARD_LOST = "card_lost"
    CARD_STOLEN = "card_stolen"


# What the student does next, as a key the app turns into a screen in any language.
RescueDoNow = Literal[
    "start_rescue",
    "answer_identity_question",
    "locked",
    "choose_card",
    "confirm_freeze",
    "confirm_transfer_or_skip",
    "done",
]


class RescueProgress(BaseModel):
    state_before: RescueState | None
    state_after: RescueState | None
    do_now: RescueDoNow
    card_names: list[str] = Field(default_factory=list)
    live_instrument: str | None = None
    issuer_link: str | None = None


class RescueReply(AgentReply):
    rescue: RescueProgress
