from collections.abc import Mapping
from datetime import datetime, timezone

from contracts.interfaces import Rail
from contracts.schemas import Receipt, ReceiptStatus, Route, TraceResult

# The Rail interface has no idempotency key argument, so mandate_ref plays that role.
FAIL_ONCE_KEY = "txn-fail-once"
# Fixture: which issuers let the fake rail freeze a card. Not a claim about the real issuers.
FREEZE_SUPPORTED = {"wise": True, "revolut": False}


class RailError(Exception):
    pass


class FakeRail(Rail):
    def __init__(self, traces: Mapping[str, TraceResult] | None = None) -> None:
        self._traces = {
            receipt_id: trace.model_copy(deep=True)
            for receipt_id, trace in (traces or {}).items()
        }
        self._receipts: dict[str, Receipt] = {}
        self._failed_once: set[str] = set()

    @property
    def name(self) -> str:
        return "fake"

    @property
    def simulated(self) -> bool:
        return True

    def execute(self, route: Route, mandate_ref: str, confirmation_token: str) -> Receipt:
        if mandate_ref in self._receipts:
            return self._receipts[mandate_ref].model_copy(deep=True)
        if mandate_ref == FAIL_ONCE_KEY and mandate_ref not in self._failed_once:
            self._failed_once.add(mandate_ref)
            raise RailError(f"Scripted failure for {mandate_ref}; nothing was charged.")
        now = datetime.now(timezone.utc)
        receipt = Receipt(
            receipt_id=f"fake-{len(self._receipts) + 1:04d}",
            rail=route.rail,
            amount=route.amount,
            currency=route.currency_from,
            status=ReceiptStatus.COMPLETED,
            stage_entered_at=now,
            mandate_ref=mandate_ref,
            simulated=True,
            executed_at=now,
        )
        self._receipts[mandate_ref] = receipt
        return receipt.model_copy(deep=True)

    def status(self, receipt_id: str) -> TraceResult:
        trace = self._traces.get(receipt_id)
        if trace is None:
            raise RailError(f"No scripted trace for receipt {receipt_id}.")
        return trace.model_copy(deep=True)

    def freeze(self, instrument_id: str) -> bool:
        issuer, separator, _ = instrument_id.partition(":")
        if not separator or issuer not in FREEZE_SUPPORTED:
            raise RailError(
                f"Unknown issuer in {instrument_id!r}; expected issuer:card, "
                f"issuer one of {sorted(FREEZE_SUPPORTED)}."
            )
        return FREEZE_SUPPORTED[issuer]
