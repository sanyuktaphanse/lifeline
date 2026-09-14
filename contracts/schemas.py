from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Corridor = Annotated[str, Field(pattern=r"^[A-Z]{2}>[A-Z]{2}$")]
PositiveAmount = Annotated[Decimal, Field(gt=0)]


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


class Action(BaseModel):
    type: ActionType
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


class Decision(BaseModel):
    allowed: bool
    reasons: list[str]
    rule_ids: list[str]
    tier: Tier
    requires_confirmation: bool = False
    warning_key: str | None = None
    confirmation_token: str | None = None
