from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import (
    FreezeResult,
    FreezeStatus,
    Receipt,
    ReceiptStatus,
    Route,
    TraceResult,
)

FAIL_ONCE_KEY = "txn-fail-once"
# Fixture: which issuers let the fake rail freeze a card. Not a claim about the real issuers.
FREEZE_SUPPORTED = {"wise": True, "revolut": False}
# Placeholder until the real Revolut deep link is sourced. The .invalid domain never resolves.
REVOLUT_FREEZE_DEEP_LINK = "https://example.invalid/revolut/freeze-card"


class FakeRail(Rail):
    def __init__(
        self,
        traces: Mapping[str, TraceResult] | None = None,
        fail_once_keys: Iterable[str] = (FAIL_ONCE_KEY,),
        name: str = "fake",
        simulated: bool = True,
    ) -> None:
        self._name = name
        self._simulated = simulated
        self._traces = {
            receipt_id: trace.model_copy(deep=True)
            for receipt_id, trace in (traces or {}).items()
        }
        self._fail_once_keys = frozenset(fail_once_keys)
        self._receipts: dict[str, Receipt] = {}
        self._requests: dict[str, tuple[dict[str, Any], str]] = {}
        self._failed_once: set[str] = set()

    @property
    def name(self) -> str:
        return self._name

    @property
    def simulated(self) -> bool:
        return self._simulated

    def execute(
        self,
        route: Route,
        mandate_ref: str,
        idempotency_key: str,
        confirmation_token: str,
    ) -> Receipt:
        request = (route.model_dump(exclude={"quoted_at"}), mandate_ref)
        if idempotency_key in self._receipts:
            if self._requests[idempotency_key] != request:
                raise RailError(
                    f"Idempotency key {idempotency_key} was already used for a different "
                    "route, amount, or mandate; nothing was charged."
                )
            return self._receipts[idempotency_key].model_copy(deep=True)
        if idempotency_key in self._fail_once_keys and idempotency_key not in self._failed_once:
            self._failed_once.add(idempotency_key)
            raise RailError(f"Scripted failure for {idempotency_key}; nothing was charged.")
        now = datetime.now(timezone.utc)
        receipt = Receipt(
            receipt_id=f"fake-{len(self._receipts) + 1:04d}",
            rail=self._name,
            amount=route.amount,
            currency=route.currency_from,
            status=ReceiptStatus.COMPLETED,
            stage_entered_at=now,
            mandate_ref=mandate_ref,
            idempotency_key=idempotency_key,
            simulated=self._simulated,
            executed_at=now,
        )
        self._receipts[idempotency_key] = receipt
        self._requests[idempotency_key] = request
        return receipt.model_copy(deep=True)

    def status(self, receipt_id: str) -> TraceResult:
        trace = self._traces.get(receipt_id)
        if trace is None:
            raise RailError(f"No scripted trace for receipt {receipt_id}.")
        return trace.model_copy(deep=True)

    def freeze(self, instrument_id: str) -> FreezeResult:
        issuer, separator, _ = instrument_id.partition(":")
        if not separator or issuer not in FREEZE_SUPPORTED:
            return FreezeResult(
                status=FreezeStatus.FAILED,
                reason=(
                    f"Unknown issuer in {instrument_id!r}; expected issuer:card, "
                    f"issuer one of {sorted(FREEZE_SUPPORTED)}."
                ),
            )
        if FREEZE_SUPPORTED[issuer]:
            return FreezeResult(status=FreezeStatus.DONE)
        return FreezeResult(
            status=FreezeStatus.NOT_SUPPORTED,
            deep_link=REVOLUT_FREEZE_DEEP_LINK,
            reason="This issuer does not let Lifeline freeze the card; freeze it in the issuer's app.",
        )
