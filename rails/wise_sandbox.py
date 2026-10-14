"""Wise's sandbox, the one rail and quote that call a provider's real API, with no real money.

The sandbox moves no money, so every route it quotes and every receipt it issues says simulated. It is used only
when `WISE_SANDBOX_TOKEN` is set; without it the API keeps its fixture Wise rail. The token lives only in `.env`,
is sent only as the Authorization header, and never appears in a repr, an error or the ledger.
Source: docs/decisions.md, 10 October 2026.
"""

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from contracts.errors import RailError
from contracts.interfaces import Rail, Router
from contracts.schemas import (
    CancelResult,
    CancelStatus,
    FreezeResult,
    FreezeStatus,
    PrecheckResult,
    Receipt,
    ReceiptStatus,
    Route,
    RouteStatus,
    TraceResult,
)

NAME = "wise"
# Source: https://docs.wise.com/api-docs/api-reference/standard-transfer, "Sandbox Environment", 10 October 2026.
SANDBOX_BASE_URL = "https://api.wise-sandbox.com/2026Q4"
SANDBOX_HOST = "api.wise-sandbox.com"
QUOTE_SOURCE = "https://docs.wise.com/api-docs/api-reference/quote"
# Source: https://docs.wise.com/api-reference/balance/balancelist, "List Balances for a Profile", 14 October 2026.
# STANDARD is the everyday balance; SAVINGS balances are not money a student spends, so they are not read.
BALANCES_SOURCE = "https://docs.wise.com/api-reference/balance/balancelist"
BALANCE_TYPES = "STANDARD"
STATUS_SOURCE = "https://docs.wise.com/guides/product/send-money/tracking/transfer-statuses"
# Lifeline's own reading of each status Wise documents at STATUS_SOURCE onto a ReceiptStatus. Wise's guide gives the
# meanings; the mapping is Lifeline's. A cancelled transfer was never funded and a refunded or charged back one went
# back to the sender, so all three are returned. A bounced back transfer will be delivered late or refunded, and an
# unknown one waits on Wise asking for more information, so both are held for review.
STATUSES: dict[str, ReceiptStatus] = {
    "incoming_payment_waiting": ReceiptStatus.CREATED,
    "incoming_payment_initiated": ReceiptStatus.CREATED,
    "processing": ReceiptStatus.FUNDED,
    "funds_converted": ReceiptStatus.IN_TRANSIT,
    "outgoing_payment_sent": ReceiptStatus.COMPLETED,
    "cancelled": ReceiptStatus.RETURNED,
    "funds_refunded": ReceiptStatus.RETURNED,
    "charged_back": ReceiptStatus.RETURNED,
    "bounced_back": ReceiptStatus.HELD_FOR_REVIEW,
    "unknown": ReceiptStatus.HELD_FOR_REVIEW,
}
SANDBOX_STEP = "This is the Wise sandbox. No real money moves."
NO_DURATION = f"Lifeline has no sourced duration on file for a Wise sandbox transfer. Statuses: {STATUS_SOURCE}."
# Source: this module. A guard so a stalled sandbox call cannot hang a student's turn; not a money rule.
TIMEOUT_SECONDS = 20.0
# Source: this module. Fixed so the same request under the same key always gives Wise the same
# customerTransactionId, which Wise uses to avoid duplicate transfers.
CUSTOMER_ID_NAMESPACE = uuid.UUID("6f1c2b0e-7c55-4c3a-9a51-6b1f1e0d9a11")
# Source: Wise's quote reference above. Lifeline funds sandbox transfers from the profile's Wise balance.
PAY_IN = "BALANCE"
REFERENCE = "Lifeline sandbox"


class WiseSandboxError(Exception):
    """A call to the Wise sandbox failed. The message carries Wise's status and reason, never the token."""


@dataclass(frozen=True)
class WiseSandboxConfig:
    token: str = field(repr=False)
    profile_id: int
    # A Lifeline payee id to the Wise recipient account id created for it in the sandbox.
    recipients: dict[str, int]
    base_url: str = SANDBOX_BASE_URL

    def __post_init__(self) -> None:
        if httpx.URL(self.base_url).host != SANDBOX_HOST:
            raise ValueError(f"The Wise sandbox client only talks to {SANDBOX_HOST}, never to production.")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "WiseSandboxConfig | None":
        """The sandbox settings from the environment, or None when no token is set."""
        token = (env.get("WISE_SANDBOX_TOKEN") or "").strip()
        if not token:
            return None
        try:
            profile_id = int((env.get("WISE_SANDBOX_PROFILE_ID") or "").strip())
        except ValueError:
            raise ValueError("WISE_SANDBOX_TOKEN is set, so WISE_SANDBOX_PROFILE_ID must be the sandbox profile's number.") from None
        recipients: dict[str, int] = {}
        for pair in (env.get("WISE_SANDBOX_RECIPIENTS") or "").split(","):
            if not pair.strip():
                continue
            payee, separator, account = pair.partition(":")
            if not separator or not account.strip().isdigit():
                raise ValueError("WISE_SANDBOX_RECIPIENTS is payee_id:recipient_account_id pairs separated by commas.")
            recipients[payee.strip()] = int(account)
        return cls(token=token, profile_id=profile_id, recipients=recipients)


def _reason(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    errors = body.get("errors") if isinstance(body, dict) else None
    if errors and isinstance(errors, list) and isinstance(errors[0], dict):
        return str(errors[0].get("message") or errors[0].get("code") or response.reason_phrase)
    if isinstance(body, dict) and body.get("message"):
        return str(body["message"])
    return response.reason_phrase


class WiseSandboxClient:
    """The Wise endpoints the rail uses. Paths from Wise's API reference, under SANDBOX_BASE_URL."""

    def __init__(self, config: WiseSandboxConfig, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self._http = httpx.Client(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.token}"},
            timeout=TIMEOUT_SECONDS,
            transport=transport,
            trust_env=False,
        )

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, json=body)
        except httpx.HTTPError as error:
            raise WiseSandboxError(f"The Wise sandbox could not be reached ({type(error).__name__}).") from None
        if response.status_code >= 400:
            raise WiseSandboxError(f"The Wise sandbox answered {response.status_code}: {_reason(response)}.")
        try:
            return response.json()
        except ValueError:
            raise WiseSandboxError(f"The Wise sandbox answered {response.status_code} with no readable body.") from None

    def quote(self, source: str, target: str, amount: Decimal, target_account: int | None = None) -> dict[str, Any]:
        # JSON has no decimal type; an amount of a student transfer has at most two places, which a float carries.
        body: dict[str, Any] = {"sourceCurrency": source, "targetCurrency": target, "sourceAmount": float(amount)}
        if target_account is not None:
            body["targetAccount"] = target_account
        return self._call("POST", f"/profiles/{self.config.profile_id}/quotes", body)

    def create_transfer(self, target_account: int, quote_id: str, customer_transaction_id: str) -> dict[str, Any]:
        return self._call(
            "POST",
            "/transfers",
            {
                "targetAccount": target_account,
                "quoteUuid": quote_id,
                "customerTransactionId": customer_transaction_id,
                "details": {"reference": REFERENCE},
            },
        )

    def fund(self, transfer_id: int) -> dict[str, Any]:
        return self._call("POST", f"/profiles/{self.config.profile_id}/transfers/{transfer_id}/payments", {"type": PAY_IN})

    def transfer(self, transfer_id: int) -> dict[str, Any]:
        return self._call("GET", f"/transfers/{transfer_id}")

    def cancel(self, transfer_id: int) -> dict[str, Any]:
        return self._call("PUT", f"/transfers/{transfer_id}/cancel")

    def simulate(self, transfer_id: int, status: str) -> dict[str, Any]:
        """Move a sandbox transfer to a status, as Wise's simulation endpoints allow. Sandbox only."""
        return self._call("GET", f"/simulation/transfers/{transfer_id}/{status}")

    def balances(self) -> dict[str, Decimal]:
        """The profile's everyday balances by currency, read from Wise: each balance's `amount`, which Wise calls the
        available balance that can fund transfers (BALANCES_SOURCE). A balance the student has hidden is left out.
        A balance with no readable amount raises, so a broken answer is never shown as zero."""
        answer = self._call("GET", f"/profiles/{self.config.profile_id}/balances?types={BALANCE_TYPES}")
        if not isinstance(answer, list):
            raise WiseSandboxError("The Wise sandbox answered the balance list with something that is not a list.")
        held: dict[str, Decimal] = {}
        for balance in answer:
            if not isinstance(balance, dict) or balance.get("visible") is False:
                continue
            amount = balance.get("amount")
            try:
                currency = str(amount["currency"])
                value = Decimal(str(amount["value"]))
            except (KeyError, TypeError, InvalidOperation):
                raise WiseSandboxError("The Wise sandbox answered a balance with no readable amount.") from None
            held[currency] = held.get(currency, Decimal("0")) + value
        return dict(sorted(held.items()))


def payment_option(quote: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The quote's option for paying in from the Wise balance, which is how the rail funds a transfer."""
    return next((o for o in quote.get("paymentOptions") or [] if o.get("payIn") == PAY_IN), None)


def _customer_transaction_id(idempotency_key: str, request: tuple[dict[str, Any], str]) -> str:
    """The same key and request always give the same id, so a retry cannot pay twice; a different request a new one."""
    return str(uuid.uuid5(CUSTOMER_ID_NAMESPACE, json.dumps([idempotency_key, request], sort_keys=True, default=str)))


class WiseSandboxRail(Rail):
    def __init__(self, client: WiseSandboxClient, recipients: Mapping[str, int]) -> None:
        self._client = client
        self._recipients = dict(recipients)
        self._receipts: dict[str, Receipt] = {}
        self._requests: dict[str, tuple[dict[str, Any], str]] = {}
        self._cancelled: set[str] = set()
        # The status each receipt was last seen at, and when it was first seen there.
        self._seen: dict[str, tuple[ReceiptStatus, datetime]] = {}

    @property
    def name(self) -> str:
        return NAME

    @property
    def simulated(self) -> bool:
        return True

    def execute(self, route: Route, mandate_ref: str, idempotency_key: str, confirmation_token: str) -> Receipt:
        request = (route.model_dump(mode="json", exclude={"quoted_at"}), mandate_ref)
        if idempotency_key in self._receipts:
            if self._requests[idempotency_key] != request:
                raise RailError(
                    f"Idempotency key {idempotency_key} was already used for a different route, amount, "
                    "or mandate; nothing was charged."
                )
            return self._receipts[idempotency_key].model_copy(deep=True)
        account = self._recipients.get(route.payee_id or "")
        if account is None:
            raise RailError(
                f"No Wise sandbox recipient is set for payee {route.payee_id!r} in WISE_SANDBOX_RECIPIENTS; "
                "nothing was charged."
            )
        try:
            quote = self._client.quote(route.currency_from, route.currency_to, route.amount, account)
            transfer = self._client.create_transfer(account, str(quote["id"]), _customer_transaction_id(idempotency_key, request))
            funding = self._client.fund(int(transfer["id"]))
            if funding.get("status") == "REJECTED":
                # The transfer stays unfunded, so a retry under the same key finds it and funds it once.
                raise RailError(
                    f"The Wise sandbox refused to fund transfer {transfer['id']}: "
                    f"{funding.get('errorCode') or 'no code given'}. Nothing was charged."
                )
            status = STATUSES.get(str(self._client.transfer(int(transfer["id"])).get("status")), ReceiptStatus.HELD_FOR_REVIEW)
        except WiseSandboxError as error:
            raise RailError(f"{error} Nothing was charged.") from None
        except (KeyError, TypeError, ValueError) as error:
            raise RailError(f"The Wise sandbox answered in a shape Lifeline does not read ({type(error).__name__}). Nothing was charged.") from None
        now = datetime.now(timezone.utc)
        receipt = Receipt(
            receipt_id=f"{NAME}-{transfer['id']}",
            rail=NAME,
            amount=route.amount,
            currency=route.currency_from,
            status=status,
            stage_entered_at=now,
            mandate_ref=mandate_ref,
            idempotency_key=idempotency_key,
            simulated=True,
            executed_at=now,
        )
        self._receipts[idempotency_key] = receipt
        self._requests[idempotency_key] = request
        self._seen[receipt.receipt_id] = (status, now)
        return receipt.model_copy(deep=True)

    def restore(self, receipt: Receipt, route: Route, mandate_ref: str) -> None:
        """Keep a receipt issued before a restart, as if issued here."""
        key = receipt.idempotency_key
        self._receipts[key] = receipt.model_copy(deep=True)
        self._requests[key] = (route.model_dump(mode="json", exclude={"quoted_at"}), mandate_ref)
        self._seen[receipt.receipt_id] = (receipt.status, receipt.stage_entered_at)

    def _issued(self, receipt_id: str) -> Receipt | None:
        return next((r for r in self._receipts.values() if r.receipt_id == receipt_id), None)

    @staticmethod
    def _transfer_id(receipt_id: str) -> int:
        return int(receipt_id.removeprefix(f"{NAME}-"))

    def status(self, receipt_id: str) -> TraceResult:
        receipt = self._issued(receipt_id)
        if receipt is None:
            raise RailError(f"No receipt {receipt_id} on the Wise sandbox rail.")
        warnings: list[str] = []
        if receipt_id in self._cancelled:
            wise_status, status = "cancelled", ReceiptStatus.RETURNED
        else:
            try:
                wise_status = str(self._client.transfer(self._transfer_id(receipt_id)).get("status"))
            except WiseSandboxError as error:
                raise RailError(str(error)) from None
            status = STATUSES.get(wise_status, ReceiptStatus.HELD_FOR_REVIEW)
            if wise_status not in STATUSES:
                warnings.append(f"Wise reported the status {wise_status}, which its guide does not list, so it is held for review.")
            elif wise_status == "bounced_back":
                warnings.append("Wise says the transfer bounced back: it will be delivered late or refunded.")
            elif wise_status == "unknown":
                warnings.append("Wise does not have enough information to finish this transfer and asks for it by email.")
        seen_status, seen_at = self._seen.get(receipt_id, (receipt.status, receipt.stage_entered_at))
        entered = seen_at if seen_status is status else datetime.now(timezone.utc)
        self._seen[receipt_id] = (status, entered)
        return TraceResult(
            receipt_id=receipt_id,
            status=status,
            stage_entered_at=entered,
            typical_duration_hours=None,
            typical_duration_source=NO_DURATION,
            next_steps=[f"Wise status: {wise_status}.", SANDBOX_STEP],
            warnings=warnings,
        )

    def simulate(self, receipt_id: str, wise_status: str) -> None:
        """Move one of this rail's sandbox transfers to a status through Wise's simulation endpoint."""
        if self._issued(receipt_id) is None:
            raise RailError(f"No receipt {receipt_id} on the Wise sandbox rail.")
        try:
            self._client.simulate(self._transfer_id(receipt_id), wise_status)
        except WiseSandboxError as error:
            raise RailError(str(error)) from None

    def freeze(self, instrument_id: str) -> FreezeResult:
        return FreezeResult(
            status=FreezeStatus.NOT_SUPPORTED,
            reason="The Wise sandbox client does not freeze cards; freeze the card in the Wise app.",
        )

    def cancel(self, receipt_id: str) -> CancelResult:
        """Ask Wise to cancel. Wise decides whether the transfer can still be cancelled, and its reason is passed on."""
        if self._issued(receipt_id) is None:
            return CancelResult(status=CancelStatus.FAILED, reason=f"The Wise sandbox rail issued no receipt {receipt_id}.")
        try:
            self._client.cancel(self._transfer_id(receipt_id))
        except WiseSandboxError as error:
            message = str(error)
            if " answered 4" in message:
                return CancelResult(status=CancelStatus.NOT_SUPPORTED, reason=message)
            return CancelResult(status=CancelStatus.FAILED, reason=message)
        self.mark_cancelled(receipt_id)
        return CancelResult(status=CancelStatus.DONE)

    def mark_cancelled(self, receipt_id: str) -> None:
        """Record a done cancel; the API calls it on start for every done cancel in the ledger."""
        receipt = self._issued(receipt_id)
        if receipt is None:
            return
        now = datetime.now(timezone.utc)
        self._cancelled.add(receipt_id)
        self._receipts[receipt.idempotency_key] = receipt.model_copy(update={"status": ReceiptStatus.RETURNED, "stage_entered_at": now})
        self._seen[receipt_id] = (ReceiptStatus.RETURNED, now)


class WiseSandboxRouter(Router):
    """Quotes every Wise route from the sandbox and leaves every other route as the inner router quoted it."""

    def __init__(self, inner: Router, client: WiseSandboxClient) -> None:
        self._inner = inner
        self._client = client

    def quote(self, corridor: str, amount: Decimal, purpose: str, urgency: str) -> list[Route]:
        return [self._sandbox(route) if route.rail == NAME else route for route in self._inner.quote(corridor, amount, purpose, urgency)]

    def precheck(self, action_kind: str, provider: str, user_context: dict[str, Any]) -> PrecheckResult:
        return self._inner.precheck(action_kind, provider, user_context)

    def _sandbox(self, route: Route) -> Route:
        # The inner router's Wise fee and arrival are fixtures; none of them survives into a sandbox route.
        base = {"simulated": True, "fee": Decimal("0"), "spread_cost": Decimal("0"), "fee_source_url": QUOTE_SOURCE}
        try:
            quote = self._client.quote(route.currency_from, route.currency_to, route.amount)
            option = payment_option(quote)
            if option is None:
                raise WiseSandboxError(f"The Wise sandbox quote offered no {PAY_IN} pay in option.")
            fee = Decimal(str(option["fee"]["total"]))
        except (WiseSandboxError, KeyError, TypeError, InvalidOperation) as error:
            reason = str(error) if isinstance(error, WiseSandboxError) else "The Wise sandbox quote could not be read."
            return route.model_copy(
                update={**base, "status": RouteStatus.DOWN, "blocked_reason": f"Wise sandbox: {reason}", "rate_source": None}
            )
        update: dict[str, Any] = {
            **base,
            "fee": fee,
            "status": RouteStatus.UP,
            "rate_source": f"Wise sandbox quote {quote['id']} at rate {quote.get('rate')}",
            "rule_id": route.rule_id,
        }
        delivery = option.get("estimatedDelivery")
        if delivery:
            arrival = datetime.fromisoformat(str(delivery).replace("Z", "+00:00"))
            update["arrival_hours"] = max(0.0, (arrival - datetime.now(timezone.utc)).total_seconds() / 3600)
        if option.get("disabled"):
            message = (option.get("disabledReason") or {}).get("message") or "no reason given"
            update.update(limit_ok=False, blocked_reason=f"Wise sandbox will not take this transfer: {message}")
        return route.model_copy(update=update)
