from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from contracts.errors import RailError
from contracts.interfaces import Rail
from contracts.schemas import (
    CancelResult,
    CancelStatus,
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
# Fixture: the statuses a fake rail still cancels from, before the money moves on. Not a claim about
# any real provider. Source: docs/decisions.md, 8 October 2026.
CANCELLABLE = (ReceiptStatus.CREATED, ReceiptStatus.FUNDED)
CANCELLED_STEP = "The student cancelled this transfer before it moved on, and it was returned."


def scripted_traces(
    traces: Mapping[str, list[Mapping[str, Any]]] | None,
) -> dict[str, dict[str, TraceResult]]:
    """Turn a fixture's traces, a rail name to a list of TraceResult fields, into traces per rail.

    A TraceResult needs a stage time and a fixture gives none, so the time is now; the rail
    replaces it with the receipt's own time once it has issued that receipt.
    """
    now = datetime.now(timezone.utc)
    return {
        rail: {
            trace["receipt_id"]: TraceResult.model_validate({"stage_entered_at": now, **trace})
            for trace in rail_traces
        }
        for rail, rail_traces in (traces or {}).items()
    }


class FakeRail(Rail):
    def __init__(
        self,
        traces: Mapping[str, TraceResult] | None = None,
        fail_once_keys: Iterable[str] = (FAIL_ONCE_KEY,),
        name: str = "fake",
        simulated: bool = True,
        issue_status: ReceiptStatus = ReceiptStatus.COMPLETED,
    ) -> None:
        self._name = name
        # Fixture: the status a receipt is issued at, completed unless a scenario chooses another.
        self._issue_status = issue_status
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
            receipt_id=f"{self._name}-{len(self._receipts) + 1:04d}",
            rail=self._name,
            amount=route.amount,
            currency=route.currency_from,
            status=self._issue_status,
            stage_entered_at=now,
            mandate_ref=mandate_ref,
            idempotency_key=idempotency_key,
            simulated=self._simulated,
            executed_at=now,
        )
        self._receipts[idempotency_key] = receipt
        self._requests[idempotency_key] = request
        return receipt.model_copy(deep=True)

    def restore(self, receipt: Receipt, route: Route, mandate_ref: str) -> None:
        key = receipt.idempotency_key
        self._receipts[key] = receipt.model_copy(deep=True)
        self._requests[key] = (route.model_dump(exclude={"quoted_at"}), mandate_ref)

    def _issued(self, receipt_id: str) -> Receipt | None:
        return next((r for r in self._receipts.values() if r.receipt_id == receipt_id), None)

    def status(self, receipt_id: str) -> TraceResult:
        trace = self._traces.get(receipt_id)
        issued = self._issued(receipt_id)
        if trace is None and issued is None:
            raise RailError(f"No scripted trace for receipt {receipt_id}.")
        if trace is None:
            # A receipt with no scripted trace is traced from itself; no entry gives a duration.
            trace = TraceResult(
                receipt_id=receipt_id,
                status=issued.status,
                stage_entered_at=issued.stage_entered_at,
                typical_duration_source="fixture: no scripted trace and no sourced duration",
                next_steps=[],
                warnings=[],
            )
        if issued is not None:
            trace = trace.model_copy(update={"stage_entered_at": issued.stage_entered_at})
        return trace.model_copy(deep=True)

    def cancel(self, receipt_id: str) -> CancelResult:
        issued = self._issued(receipt_id)
        if issued is None:
            return CancelResult(status=CancelStatus.FAILED, reason=f"{self._name} issued no receipt {receipt_id}.")
        # What the student is shown is what the rail answers on: the scripted trace when there is one.
        current = self._traces[receipt_id].status if receipt_id in self._traces else issued.status
        if current not in CANCELLABLE:
            return CancelResult(
                status=CancelStatus.NOT_SUPPORTED,
                reason=f"This transfer is {current.value.replace('_', ' ')}, so it can no longer be cancelled through Lifeline.",
            )
        self.mark_cancelled(receipt_id)
        return CancelResult(status=CancelStatus.DONE)

    def mark_cancelled(self, receipt_id: str) -> None:
        """Record a done cancel: the receipt is returned and its trace says the student cancelled it.

        The API calls it on start for every done cancel in the ledger, so a restart keeps it."""
        issued = self._issued(receipt_id)
        if issued is None:
            return
        now = datetime.now(timezone.utc)
        returned = issued.model_copy(update={"status": ReceiptStatus.RETURNED, "stage_entered_at": now})
        self._receipts[issued.idempotency_key] = returned
        base = self._traces.get(receipt_id)
        self._traces[receipt_id] = TraceResult(
            receipt_id=receipt_id,
            status=ReceiptStatus.RETURNED,
            stage_entered_at=now,
            typical_duration_hours=None,
            typical_duration_source=base.typical_duration_source if base else "fixture: no sourced duration",
            next_steps=[CANCELLED_STEP],
            warnings=[],
        )

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
