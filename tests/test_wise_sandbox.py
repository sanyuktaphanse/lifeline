"""The Wise sandbox rail and quotes, against a fake Wise server: no test reaches the network."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from contracts.errors import RailError
from contracts.interfaces import Rail, Router
from contracts.schemas import CancelStatus, FreezeStatus, Message, ReceiptStatus, Role, RouteStatus, ToolCall
from core.fake_adapter import FakeModelAdapter
from rails.fake_router import FakeRouter
from rails.wise_sandbox import (
    SANDBOX_BASE_URL,
    SCA_REFUSED,
    STATUS_SOURCE,
    WiseSandboxClient,
    WiseSandboxConfig,
    WiseSandboxError,
    WiseSandboxRail,
    WiseSandboxRouter,
)

TOKEN = "sandbox-token-for-tests-only"
# The profile, recipient account, quote and transfer ids are the example values in Wise's own API reference
# (https://docs.wise.com/api-docs/api-reference/standard-transfer and .../quote), or made up, such as 555; none is an id from a real account.
PROFILE = 101
RECIPIENTS = {"landlord_sp": 8692237, "self_sg": 555}


class FakeWise:
    """Answers the Wise endpoints the rail uses, keeping transfers by id, as the sandbox would."""

    def __init__(
        self, fee="5.31", disabled=False, fund_status="COMPLETED", cancel_code=200, quote_code=200, balances=None, balances_code=200,
        fund_code=201, fund_sca=False,
    ):
        self.fee = fee
        self.disabled = disabled
        self.fund_status = fund_status
        # fund_code 403 with fund_sca answers as Wise's sandbox did on 16 October 2026 for a personal account: the
        # strong customer authentication headers and the body {"error": "forbidden"}. Without fund_sca, a bare 403.
        self.fund_code = fund_code
        self.fund_sca = fund_sca
        self.cancel_code = cancel_code
        self.quote_code = quote_code
        self.balances = balances if balances is not None else []
        self.balances_code = balances_code
        self.transfers: dict[int, dict] = {}
        self.by_customer_id: dict[str, int] = {}
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/2026Q4")
        body = json.loads(request.content) if request.content else {}
        if request.method == "POST" and path == f"/profiles/{PROFILE}/quotes":
            if self.quote_code != 200:
                return httpx.Response(self.quote_code, json={"errors": [{"message": "Quote not available"}]})
            delivery = (datetime.now(timezone.utc) + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
            option = {
                "disabled": self.disabled,
                "disabledReason": {"message": "Amount too high"} if self.disabled else None,
                "estimatedDelivery": delivery,
                "fee": {"total": float(self.fee)},
                "payIn": "BALANCE",
                "payOut": "BANK_TRANSFER",
                "sourceAmount": body["sourceAmount"],
            }
            return httpx.Response(200, json={"id": "11144c35-9fe8-4c32-b7fd-d05c2a7734bf", "rate": 3.9, "paymentOptions": [option]})
        if request.method == "POST" and path == "/transfers":
            existing = self.by_customer_id.get(body["customerTransactionId"])
            if existing is None:
                existing = 16521632 + len(self.transfers)
                self.by_customer_id[body["customerTransactionId"]] = existing
                self.transfers[existing] = {"id": existing, "status": "incoming_payment_waiting", **body}
            return httpx.Response(200, json=self.transfers[existing])
        if request.method == "POST" and path.endswith("/payments"):
            transfer_id = int(path.split("/")[4])
            if self.fund_code == 403:
                headers = {"x-2fa-approval-result": "REJECTED", "x-2fa-approval": "made-up-approval-id"} if self.fund_sca else {}
                return httpx.Response(403, headers=headers, json={"error": "forbidden"})
            if self.fund_status != "REJECTED":
                self.transfers[transfer_id]["status"] = "processing"
            return httpx.Response(201, json={"type": "BALANCE", "status": self.fund_status, "errorCode": "insufficient.funds" if self.fund_status == "REJECTED" else None})
        if request.method == "PUT" and path.endswith("/cancel"):
            transfer_id = int(path.split("/")[2])
            if self.cancel_code != 200:
                return httpx.Response(self.cancel_code, json={"errors": [{"message": "Transfer cannot be cancelled"}]})
            self.transfers[transfer_id]["status"] = "cancelled"
            return httpx.Response(200, json=self.transfers[transfer_id])
        if request.method == "GET" and path.startswith("/transfers/"):
            transfer_id = int(path.split("/")[2])
            if transfer_id not in self.transfers:
                return httpx.Response(404, json={"errors": [{"message": "Transfer not found"}]})
            return httpx.Response(200, json=self.transfers[transfer_id])
        if request.method == "GET" and path == f"/profiles/{PROFILE}/balances":
            if self.balances_code != 200:
                return httpx.Response(self.balances_code, json={"errors": [{"message": "Balances not available"}]})
            return httpx.Response(200, json=self.balances)
        if request.method == "GET" and path.startswith("/simulation/transfers/"):
            _, _, _, transfer_id, status = path.split("/")
            self.transfers[int(transfer_id)]["status"] = status
            return httpx.Response(200, json=self.transfers[int(transfer_id)])
        return httpx.Response(404, json={"errors": [{"message": f"No route {request.method} {path}"}]})


def _config():
    return WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients=dict(RECIPIENTS))


def _client(wise):
    return WiseSandboxClient(_config(), transport=httpx.MockTransport(wise.handler))


def _rail(wise=None):
    wise = wise or FakeWise()
    return WiseSandboxRail(_client(wise), RECIPIENTS), wise


def _route(corridor="SG>BR", amount="1200", payee="landlord_sp"):
    route = next(r for r in FakeRouter().quote(corridor, Decimal(amount), "rent", "normal") if r.rail == "wise")
    return route.model_copy(update={"payee_id": payee})


# Configuration


def test_no_token_means_no_sandbox_and_the_api_keeps_its_fake():
    assert WiseSandboxConfig.from_env({}) is None
    assert WiseSandboxConfig.from_env({"WISE_SANDBOX_TOKEN": "  "}) is None


def test_the_config_reads_the_profile_and_the_recipients_by_payee_id():
    config = WiseSandboxConfig.from_env(
        {
            "WISE_SANDBOX_TOKEN": TOKEN,
            "WISE_SANDBOX_PROFILE_ID": "101",
            "WISE_SANDBOX_RECIPIENTS": "landlord_sp:8692237, self_sg:555",
        }
    )

    assert config.profile_id == 101
    assert config.recipients == RECIPIENTS
    assert config.base_url == SANDBOX_BASE_URL


@pytest.mark.parametrize(
    "env",
    [
        {"WISE_SANDBOX_TOKEN": TOKEN},
        {"WISE_SANDBOX_TOKEN": TOKEN, "WISE_SANDBOX_PROFILE_ID": "abc"},
        {"WISE_SANDBOX_TOKEN": TOKEN, "WISE_SANDBOX_PROFILE_ID": "101", "WISE_SANDBOX_RECIPIENTS": "landlord_sp"},
    ],
)
def test_a_token_with_a_broken_profile_or_recipient_list_is_an_error_not_a_silent_fake(env):
    with pytest.raises(ValueError):
        WiseSandboxConfig.from_env(env)


def test_the_sandbox_host_comes_from_wises_api_reference_and_is_never_production():
    assert SANDBOX_BASE_URL == "https://api.wise-sandbox.com/2026Q4"
    with pytest.raises(ValueError):
        WiseSandboxConfig(token=TOKEN, profile_id=PROFILE, recipients={}, base_url="https://api.wise.com/2026Q4")


def test_the_token_never_appears_in_the_config_repr_or_in_an_error():
    wise = FakeWise(quote_code=500)
    assert TOKEN not in repr(_config())
    with pytest.raises(WiseSandboxError) as error:
        _client(wise).quote("SGD", "BRL", Decimal("100"))
    assert TOKEN not in str(error.value)
    assert wise.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"


# The rail


def test_the_rail_is_named_wise_and_says_it_is_simulated():
    rail, _ = _rail()

    assert isinstance(rail, Rail)
    assert (rail.name, rail.simulated) == ("wise", True)


def test_execute_quotes_creates_and_funds_one_transfer_and_issues_a_simulated_receipt():
    rail, wise = _rail()

    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    assert receipt.receipt_id == "wise-16521632"
    assert receipt.rail == "wise"
    assert receipt.simulated is True
    assert (receipt.amount, receipt.currency) == (Decimal("1200"), "SGD")
    assert receipt.status is ReceiptStatus.FUNDED
    created = json.loads(next(r for r in wise.requests if r.url.path.endswith("/transfers")).content)
    assert created["targetAccount"] == RECIPIENTS["landlord_sp"]
    assert created["quoteUuid"] == "11144c35-9fe8-4c32-b7fd-d05c2a7734bf"
    assert [r.method + " " + r.url.path.split("/")[-1] for r in wise.requests] == [
        "POST quotes", "POST transfers", "POST payments", "GET 16521632",
    ]


def test_the_same_key_and_request_returns_the_first_receipt_without_calling_wise_again():
    rail, wise = _rail()
    first = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    calls = len(wise.requests)

    again = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    assert again == first
    assert len(wise.requests) == calls


def test_the_same_key_with_a_different_amount_raises_and_charges_nothing():
    rail, wise = _rail()
    rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    with pytest.raises(RailError, match="already used"):
        rail.execute(_route(amount="1300"), "mandate-student_001-v1", "wise-key-0001", "token")
    assert len(wise.transfers) == 1


def test_the_customer_transaction_id_is_stable_for_a_retry_and_differs_for_a_different_request():
    rail, wise = _rail(FakeWise(fund_status="REJECTED"))
    with pytest.raises(RailError):
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    wise.fund_status = "COMPLETED"

    rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    rail.execute(_route(amount="50"), "mandate-student_001-v1", "wise-key-0002", "token")

    ids = [json.loads(r.content)["customerTransactionId"] for r in wise.requests if r.url.path.endswith("/transfers")]
    assert ids[0] == ids[1]
    assert ids[2] != ids[0]
    assert len(wise.transfers) == 2


def test_a_payee_with_no_sandbox_recipient_is_refused_before_wise_is_called():
    rail, wise = _rail()

    with pytest.raises(RailError, match="WISE_SANDBOX_RECIPIENTS"):
        rail.execute(_route(payee="stranger"), "mandate-student_001-v1", "wise-key-0001", "token")
    assert wise.requests == []


def test_a_rejected_funding_raises_with_wises_code_and_leaves_the_transfer_unfunded_for_a_retry():
    rail, wise = _rail(FakeWise(fund_status="REJECTED"))

    with pytest.raises(RailError, match="insufficient.funds") as error:
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    assert "Nothing was charged" in str(error.value)
    assert wise.transfers[16521632]["status"] == "incoming_payment_waiting"


SCA_SENTENCE = (
    "Wise asked for strong customer authentication to fund the transfer, which Wise no longer allows a personal "
    "account to complete by API; the payment can only be funded in Wise's own app."
)


def test_a_funding_refused_for_strong_customer_authentication_says_so():
    with pytest.raises(WiseSandboxError) as error:
        _client(FakeWise(fund_code=403, fund_sca=True)).fund(16521632)

    assert str(error.value) == SCA_SENTENCE == SCA_REFUSED
    assert TOKEN not in str(error.value)


def test_a_403_without_the_strong_customer_authentication_header_keeps_the_existing_message():
    with pytest.raises(WiseSandboxError) as error:
        _client(FakeWise(fund_code=403)).fund(16521632)

    assert str(error.value) == "The Wise sandbox answered 403: Forbidden."


def test_a_refused_funding_cancels_the_draft_transfer_and_the_error_names_it():
    rail, wise = _rail(FakeWise(fund_code=403, fund_sca=True))

    with pytest.raises(RailError) as error:
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    assert str(error.value).startswith(
        f"Wise created transfer 16521632, status incoming_payment_waiting, and refused to fund it: {SCA_SENTENCE}"
    )
    assert wise.transfers[16521632]["status"] == "cancelled"
    assert [r.method + " " + r.url.path.split("/")[-1] for r in wise.requests][-1] == "PUT cancel"


def test_a_refused_funding_whose_cancel_also_fails_still_reports_the_refusal():
    rail, wise = _rail(FakeWise(fund_code=403, fund_sca=True, cancel_code=422))

    with pytest.raises(RailError, match="refused to fund it: Wise asked for strong customer authentication"):
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    assert wise.transfers[16521632]["status"] == "incoming_payment_waiting"


def test_a_refused_funding_reaches_the_ledger_with_the_transfer_id_and_writes_no_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("COUNCIL", "")
    wise = FakeWise(fund_code=403, fund_sca=True)
    allowance = {"amount": "25", "currency": "SGD", "corridor": "SG>SG", "payee_id": "self_sg", "purpose": "emergency"}
    call = Message(
        role=Role.ASSISTANT, text="", tool_calls=[ToolCall(id="call_1", name="propose_transfer", arguments=allowance)],
        provider="fake", model="fake",
    )
    api = TestClient(
        create_app(
            adapter=FakeModelAdapter([call]),
            ledger_path=tmp_path / "ledger.jsonl",
            conversations_path=tmp_path / "conversations.jsonl",
            tick_seconds=None,
            wise_sandbox=_client(wise),
        )
    )

    proposed = api.post("/chat", json={"user_id": "student_001", "text": "Send 25 SGD to my own account, emergency"}).json()
    reply = api.post(
        "/confirm", json={"user_id": "student_001", "confirmation_token": proposed["confirmation"]["confirmation_token"]}
    ).json()

    entries = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    errors = [e["payload"]["rail_error"] for e in entries if e["kind"] == "note" and "rail_error" in e["payload"]]
    assert errors and "Wise created transfer 16521632, status incoming_payment_waiting" in errors[0]
    assert SCA_SENTENCE in errors[0]
    assert not any(e["kind"] == "receipt" for e in entries)
    assert reply.get("receipt") is None
    assert "16521632" in reply["text"]
    assert wise.transfers[16521632]["status"] == "cancelled"


def test_a_wise_error_becomes_a_rail_error_and_records_no_key():
    rail, wise = _rail(FakeWise(quote_code=503))

    with pytest.raises(RailError, match="503"):
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    wise.quote_code = 200

    receipt = rail.execute(_route(amount="1300"), "mandate-student_001-v1", "wise-key-0001", "token")
    assert receipt.amount == Decimal("1300")


def test_a_network_failure_becomes_a_rail_error():
    def down(request):
        raise httpx.ConnectError("no route to host", request=request)

    rail = WiseSandboxRail(WiseSandboxClient(_config(), transport=httpx.MockTransport(down)), RECIPIENTS)

    with pytest.raises(RailError, match="could not be reached"):
        rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")


# Trace


@pytest.mark.parametrize(
    ("wise_status", "expected"),
    [
        ("incoming_payment_waiting", ReceiptStatus.CREATED),
        ("incoming_payment_initiated", ReceiptStatus.CREATED),
        ("processing", ReceiptStatus.FUNDED),
        ("funds_converted", ReceiptStatus.IN_TRANSIT),
        ("outgoing_payment_sent", ReceiptStatus.COMPLETED),
        ("cancelled", ReceiptStatus.RETURNED),
        ("funds_refunded", ReceiptStatus.RETURNED),
        ("charged_back", ReceiptStatus.RETURNED),
        ("bounced_back", ReceiptStatus.HELD_FOR_REVIEW),
        ("unknown", ReceiptStatus.HELD_FOR_REVIEW),
    ],
)
def test_every_wise_status_maps_onto_a_receipt_status(wise_status, expected):
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    wise.transfers[16521632]["status"] = wise_status

    trace = rail.status(receipt.receipt_id)

    assert trace.status is expected
    assert trace.next_steps[0] == f"Wise status: {wise_status}."
    assert "sandbox" in trace.next_steps[1]
    assert trace.typical_duration_hours is None
    assert STATUS_SOURCE in trace.typical_duration_source


def test_a_status_wise_has_not_documented_is_held_with_a_warning_naming_it():
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    wise.transfers[16521632]["status"] = "something_new"

    trace = rail.status(receipt.receipt_id)

    assert trace.status is ReceiptStatus.HELD_FOR_REVIEW
    assert any("something_new" in warning for warning in trace.warnings)


def test_the_sandbox_simulation_moves_a_transfer_along_and_the_trace_follows_it():
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    rail.simulate(receipt.receipt_id, "funds_converted")
    assert rail.status(receipt.receipt_id).status is ReceiptStatus.IN_TRANSIT
    rail.simulate(receipt.receipt_id, "outgoing_payment_sent")
    assert rail.status(receipt.receipt_id).status is ReceiptStatus.COMPLETED


def test_a_receipt_this_rail_never_issued_is_a_rail_error():
    rail, _ = _rail()

    with pytest.raises(RailError):
        rail.status("wise-0001")


# Cancel, freeze and restore


def test_a_cancel_wise_accepts_is_done_and_the_receipt_is_returned():
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    result = rail.cancel(receipt.receipt_id)

    assert result.status is CancelStatus.DONE
    assert rail.status(receipt.receipt_id).status is ReceiptStatus.RETURNED


def test_a_cancel_wise_refuses_is_not_supported_with_wises_reason():
    rail, wise = _rail(FakeWise(cancel_code=422))
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")

    result = rail.cancel(receipt.receipt_id)

    assert result.status is CancelStatus.NOT_SUPPORTED
    assert "Transfer cannot be cancelled" in result.reason


def test_a_cancel_of_a_receipt_this_rail_never_issued_fails():
    rail, _ = _rail()

    assert rail.cancel("wise-9").status is CancelStatus.FAILED


def test_the_sandbox_client_freezes_no_card_and_says_so():
    rail, _ = _rail()

    result = rail.freeze("wise:card_01")

    assert result.status is FreezeStatus.NOT_SUPPORTED
    assert result.deep_link is None
    assert "Wise app" in result.reason


def test_a_restored_receipt_is_traced_and_repeats_without_calling_wise_for_a_new_transfer():
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    fresh, _ = _rail(wise)

    fresh.restore(receipt, _route(), "mandate-student_001-v1")
    before = len(wise.transfers)

    assert fresh.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token") == receipt
    assert fresh.status(receipt.receipt_id).status is ReceiptStatus.FUNDED
    assert len(wise.transfers) == before


def test_a_cancel_recorded_in_the_ledger_stays_cancelled_after_a_restart():
    rail, wise = _rail()
    receipt = rail.execute(_route(), "mandate-student_001-v1", "wise-key-0001", "token")
    fresh, _ = _rail(wise)
    fresh.restore(receipt, _route(), "mandate-student_001-v1")

    fresh.mark_cancelled(receipt.receipt_id)

    assert fresh.status(receipt.receipt_id).status is ReceiptStatus.RETURNED


# The router


def _router(wise):
    return WiseSandboxRouter(FakeRouter(), _client(wise))


def test_the_router_replaces_the_fixture_wise_route_with_the_sandbox_quote():
    router = _router(FakeWise(fee="5.31"))

    routes = router.quote("SG>BR", Decimal("1200"), "rent", "normal")
    wise = next(r for r in routes if r.rail == "wise")

    assert isinstance(router, Router)
    assert wise.fee == Decimal("5.31")
    assert wise.simulated is True
    assert wise.status is RouteStatus.UP
    assert "11144c35-9fe8-4c32-b7fd-d05c2a7734bf" in wise.rate_source
    assert wise.fee_source_url is not None
    assert 19 <= wise.arrival_hours <= 20
    assert wise.purpose == "rent"
    assert {r.rail for r in routes} == {"wise", "sim_pix", "bank_wire"}


def test_the_router_leaves_every_other_route_exactly_as_the_inner_router_quoted_it():
    routes = _router(FakeWise()).quote("SG>BR", Decimal("1200"), "rent", "normal")
    inner = FakeRouter().quote("SG>BR", Decimal("1200"), "rent", "normal")

    strip = lambda rs: [r.model_dump(exclude={"quoted_at"}) for r in rs if r.rail != "wise"]
    assert strip(routes) == strip(inner)


def test_a_disabled_payment_option_is_returned_blocked_with_wises_reason():
    route = next(r for r in _router(FakeWise(disabled=True)).quote("SG>SG", Decimal("300"), "emergency", "normal"))

    assert route.limit_ok is False
    assert "Amount too high" in route.blocked_reason


def test_a_sandbox_that_cannot_quote_returns_the_route_down_never_the_fixture_fee():
    route = next(r for r in _router(FakeWise(quote_code=500)).quote("SG>SG", Decimal("300"), "emergency", "normal"))

    assert route.status is RouteStatus.DOWN
    assert route.simulated is True
    assert route.fee == Decimal("0")
    assert "Wise sandbox" in route.blocked_reason


def test_the_router_passes_prechecks_to_the_inner_router():
    router = _router(FakeWise())

    assert router.precheck("enable_pix", "nubank", {}) == FakeRouter().precheck("enable_pix", "nubank", {})


# Balances


def _balance(currency, value, visible=True, kind="STANDARD"):
    # The fields of a balance in Wise's reference, https://docs.wise.com/api-reference/balance/balancelist; the
    # values are made up.
    return {"id": 200 + len(currency), "currency": currency, "type": kind, "name": None, "visible": visible,
            "amount": {"value": value, "currency": currency}, "reservedAmount": {"value": 0, "currency": currency}}


def test_balances_read_the_profiles_standard_balances_by_currency_as_decimals():
    wise = FakeWise(balances=[_balance("SGD", 2300.5), _balance("BRL", 150)])
    assert _client(wise).balances() == {"BRL": Decimal("150"), "SGD": Decimal("2300.5")}
    request = wise.requests[-1]
    assert request.method == "GET"
    assert request.url.path == f"/2026Q4/profiles/{PROFILE}/balances"
    assert request.url.params["types"] == "STANDARD"


def test_a_balance_the_student_has_hidden_is_left_out():
    wise = FakeWise(balances=[_balance("SGD", 10), _balance("EUR", 99, visible=False)])
    assert _client(wise).balances() == {"SGD": Decimal("10")}


def test_a_balance_with_no_readable_amount_is_an_error_not_a_zero():
    broken = _balance("SGD", 10)
    del broken["amount"]
    with pytest.raises(WiseSandboxError, match="balance"):
        _client(FakeWise(balances=[broken])).balances()


def test_a_refused_balances_call_raises_with_wises_reason_and_no_token():
    with pytest.raises(WiseSandboxError) as error:
        _client(FakeWise(balances_code=403)).balances()
    assert "403" in str(error.value) and "Balances not available" in str(error.value)
    assert TOKEN not in str(error.value)
