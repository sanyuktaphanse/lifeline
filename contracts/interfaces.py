from abc import ABC, abstractmethod
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from contracts.schemas import (
    Action,
    Decision,
    LedgerEntry,
    Mandate,
    Message,
    PrecheckResult,
    Receipt,
    Route,
    TraceResult,
)


class MandateEngine(ABC):
    @abstractmethod
    def check(
        self, action: Action, mandate: Mandate, history: Sequence[Action] = ()
    ) -> Decision: ...

    @abstractmethod
    def confirmation_token_for(self, action: Action, mandate: Mandate) -> str: ...


class Ledger(ABC):
    @abstractmethod
    def append(self, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry: ...

    @abstractmethod
    def verify(self) -> int | None: ...

    @abstractmethod
    def entries(self) -> list[LedgerEntry]: ...

    @abstractmethod
    def head(self) -> str: ...


class Anchor(ABC):
    @abstractmethod
    def anchor(self, head_hash: str, seq: int, user_hash: str) -> str: ...

    @abstractmethod
    def verify(self, head_hash: str) -> bool: ...


class Router(ABC):
    @abstractmethod
    def quote(
        self, corridor: str, amount: Decimal, purpose: str, urgency: str
    ) -> list[Route]: ...

    @abstractmethod
    def precheck(
        self, action_kind: str, provider: str, user_context: dict[str, Any]
    ) -> PrecheckResult: ...


class Rail(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def simulated(self) -> bool: ...

    @abstractmethod
    def execute(
        self, route: Route, mandate_ref: str, confirmation_token: str
    ) -> Receipt: ...

    @abstractmethod
    def status(self, receipt_id: str) -> TraceResult: ...

    @abstractmethod
    def freeze(self, instrument_id: str) -> bool: ...


class Council(ABC):
    @abstractmethod
    def deliberate(self, question: str, context: dict[str, Any]) -> dict[str, Any]: ...


class ModelAdapter(ABC):
    @abstractmethod
    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
    ) -> Message: ...


class Translator(ABC):
    @abstractmethod
    def explain(self, text: str, source_lang: str, target_lang: str) -> str: ...
