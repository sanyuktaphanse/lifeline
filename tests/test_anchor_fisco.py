"""The FISCO BCOS anchor behind the same Anchor interface as the local one. Every test here fakes the
transport, so none needs a network or docker; the integration test at the end is skipped unless a node
answers at FISCO_RPC_URL."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from contracts.interfaces import Anchor
from core.anchor_fisco import (
    CONFIG_VARS,
    ChainRecord,
    ChainTransport,
    FiscoAnchorError,
    FiscoBcosAnchor,
    JsonRpcTransport,
    TransportUnavailable,
)
from core.anchor_local import AnchorNotConfigured
from core.evm_tx import address_of

ROOT = Path(__file__).resolve().parent.parent
HEAD = hashlib.sha256(b"head").hexdigest()
USER = hashlib.sha256(b"student_001").hexdigest()
TX = "0x" + "ab" * 32
OURS = address_of(bytes.fromhex("46" * 32))
KEY = "46" * 32
CONFIG = {"FISCO_RPC_URL": "http://127.0.0.1:20200", "FISCO_CONTRACT_ADDRESS": "0x" + "12" * 20, "FISCO_KEY_PATH": "/keys/anchor.pem"}


class FakeTransport(ChainTransport):
    def __init__(self, fail: Exception | None = None) -> None:
        self.records: dict[str, ChainRecord] = {}
        self.seen: list[tuple[str, str, int, str]] = []
        self.fail = fail

    def send_anchor(self, config, head_hash, seq, user_hash):
        if self.fail is not None:
            raise self.fail
        self.seen.append((config.key_path, head_hash, seq, user_hash))
        self.records[head_hash] = ChainRecord(head_hash, seq, user_hash, datetime(2026, 10, 8, 12, tzinfo=timezone.utc), OURS, 42)
        return TX

    def read_record(self, config, head_hash):
        if self.fail is not None:
            raise self.fail
        return self.records.get(head_hash)


class Unavailable(ChainTransport):
    def send_anchor(self, config, head_hash, seq, user_hash):
        raise TransportUnavailable("no python sdk")

    def read_record(self, config, head_hash):
        raise TransportUnavailable("no python sdk")


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for name, value in CONFIG.items():
        monkeypatch.setenv(name, value)
    key = tmp_path / "anchor.key"
    key.write_text(KEY + "\n")
    monkeypatch.setenv("FISCO_KEY_PATH", str(key))
    return key


def test_the_fisco_anchor_implements_the_anchor_interface():
    assert issubclass(FiscoBcosAnchor, Anchor)
    assert FiscoBcosAnchor.kind == "fisco"


def test_a_successful_anchor_returns_the_transaction_hash(configured):
    transport = FakeTransport()

    anchor_id = FiscoBcosAnchor(transports=[transport]).anchor(HEAD, 7, USER)

    assert anchor_id == f"fisco:{TX}"
    assert transport.seen == [(str(configured), HEAD, 7, USER)]


def test_verify_reads_back_the_record_with_its_time_and_block(configured):
    anchor = FiscoBcosAnchor(transports=[FakeTransport()])
    anchor.anchor(HEAD, 7, USER)

    assert anchor.verify(HEAD) is True
    assert anchor.anchored_at(HEAD) == datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    assert anchor.block_number(HEAD) == 42
    other = hashlib.sha256(b"other").hexdigest()
    assert anchor.verify(other) is False
    assert anchor.anchored_at(other) is None and anchor.block_number(other) is None


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), RuntimeError("node said no"), ValueError("bad reply")])
def test_a_transport_error_becomes_the_anchors_own_error(configured, error):
    anchor = FiscoBcosAnchor(transports=[FakeTransport(fail=error)])

    with pytest.raises(FiscoAnchorError):
        anchor.anchor(HEAD, 7, USER)
    with pytest.raises(FiscoAnchorError):
        anchor.verify(HEAD)


@pytest.mark.parametrize("missing", CONFIG_VARS)
def test_a_missing_configuration_raises_not_configured_naming_the_variable(configured, monkeypatch, missing):
    monkeypatch.setenv(missing, "")

    with pytest.raises(AnchorNotConfigured, match=missing):
        FiscoBcosAnchor(transports=[FakeTransport()]).anchor(HEAD, 7, USER)


def test_the_configuration_is_read_at_call_time(configured, monkeypatch):
    transport = FakeTransport()
    anchor = FiscoBcosAnchor(transports=[transport])
    anchor.anchor(HEAD, 7, USER)
    monkeypatch.setenv("FISCO_KEY_PATH", "/keys/rotated.pem")

    anchor.anchor(hashlib.sha256(b"next").hexdigest(), 8, USER)

    assert [seen[0] for seen in transport.seen] == [str(configured), "/keys/rotated.pem"]


def test_the_python_route_is_tried_first_and_json_rpc_second(configured):
    second = FakeTransport()

    assert FiscoBcosAnchor(transports=[Unavailable(), second]).anchor(HEAD, 7, USER) == f"fisco:{TX}"
    assert second.seen


def test_with_no_route_available_the_anchor_is_not_configured_and_says_what_was_tried(configured):
    with pytest.raises(AnchorNotConfigured, match="no python sdk"):
        FiscoBcosAnchor(transports=[Unavailable(), Unavailable()]).anchor(HEAD, 7, USER)


@pytest.mark.parametrize(
    ("head", "seq", "user"),
    [("not a hash", 1, USER), (HEAD, -1, USER), (HEAD, True, USER), (HEAD, 1, "student_001")],
)
def test_only_hashes_and_a_sequence_reach_the_chain(configured, head, seq, user):
    transport = FakeTransport()

    with pytest.raises(ValueError):
        FiscoBcosAnchor(transports=[transport]).anchor(head, seq, user)
    assert transport.seen == []


def test_the_key_never_appears_in_an_error(configured, monkeypatch, tmp_path):
    key = tmp_path / "anchor.pem"
    key.write_text("-----BEGIN PRIVATE KEY-----\nSECRET-KEY-MATERIAL\n-----END PRIVATE KEY-----\n")
    monkeypatch.setenv("FISCO_KEY_PATH", str(key))
    anchor = FiscoBcosAnchor(transports=[FakeTransport(fail=RuntimeError("signing failed"))])

    with pytest.raises(FiscoAnchorError) as raised:
        anchor.anchor(HEAD, 7, USER)

    assert "SECRET-KEY-MATERIAL" not in str(raised.value)


def test_the_json_rpc_transport_posts_with_a_short_timeout_through_its_adapter(configured):
    calls = []

    def post(url, payload, timeout):
        calls.append((url, payload["method"], timeout))
        raise httpx.ConnectError("refused")

    anchor = FiscoBcosAnchor(transports=[JsonRpcTransport(post=post)])
    with pytest.raises(FiscoAnchorError):
        anchor.verify(HEAD)

    assert calls and calls[0][0] == CONFIG["FISCO_RPC_URL"]
    assert calls[0][2] <= 5


def test_the_env_example_names_the_three_variables_with_no_values():
    lines = (ROOT / ".env.example").read_text().splitlines()

    for name in CONFIG_VARS:
        assert f"{name}=" in lines


def test_the_contract_holds_only_hashes_a_sequence_a_time_and_a_sender():
    source = (ROOT / "chain" / "LifelineEvidence.sol").read_text()
    code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("//")).casefold()

    for word in ("payable", "balance", "amount", "payee", "transfer(", "string"):
        assert word not in code, word
    assert "function anchor(bytes32 head, uint64 seq, bytes32 userhash)" in code
    assert "function verify(bytes32 head)" in code
    assert "no funds" in source


def _node_answers() -> bool:
    url = os.environ.get("FISCO_RPC_URL")
    if not url:
        return False
    try:
        httpx.post(url, json={"jsonrpc": "2.0", "method": "getBlockNumber", "params": [], "id": 1}, timeout=2)
    except httpx.HTTPError:
        return False
    return True


@pytest.mark.skipif(not _node_answers(), reason="No FISCO BCOS node answers at FISCO_RPC_URL.")
def test_a_real_node_anchors_a_head_and_verifies_it_with_a_block_number():
    head = hashlib.sha256(datetime.now(timezone.utc).isoformat().encode()).hexdigest()
    anchor = FiscoBcosAnchor()

    anchor_id = anchor.anchor(head, 1, USER)

    assert anchor_id.startswith("fisco:0x")
    assert anchor.verify(head) is True
    assert anchor.block_number(head) >= 1


def test_the_verify_endpoint_shows_the_block_number_and_the_kind_fisco(configured, monkeypatch, tmp_path):
    import api.main
    from fastapi.testclient import TestClient

    from core.fake_adapter import FakeModelAdapter
    from tests.test_api import RENT, RENT_REQUEST, USER, _call

    monkeypatch.setattr(api.main, "LEDGER_PATH", tmp_path / "data" / "ledger.jsonl")
    monkeypatch.setattr(api.main, "CONVERSATIONS_PATH", tmp_path / "data" / "conversations.jsonl")
    monkeypatch.setenv("COUNCIL", "")
    client = TestClient(api.main.create_app(adapter=FakeModelAdapter([_call("propose_transfer", RENT)]), anchor=FiscoBcosAnchor(transports=[FakeTransport()])))
    token = client.post("/chat", json={"user_id": USER, "text": RENT_REQUEST}).json()["confirmation"]["confirmation_token"]
    client.post("/confirm", json={"user_id": USER, "confirmation_token": token})

    anchor = client.get(f"/ledger/{USER}/verify").json()["anchor"]

    assert anchor["kind"] == "fisco"
    assert anchor["verified"] is True and anchor["matches_ledger"] is True
    assert anchor["block_number"] == 42
    assert anchor["anchored_at"] == "2026-10-08T12:00:00+00:00"
    assert "development_secret" not in anchor


def test_a_chain_that_cannot_be_read_is_reported_as_not_verified_with_its_error(configured):
    from core.agent import AgentLoop
    from core.ledger import HashChainLedger
    from core.mandate import DeterministicMandateEngine
    from rails.fake_router import FakeRouter

    ledger = HashChainLedger()
    head = ledger.append("agent", "turn", {"user_id": "student_001", "turn": 1})
    ledger.append("agent", "anchor", {"user_id": "student_001", "head_hash": head.hash, "head_seq": head.seq, "anchor_id": "fisco:0x1", "anchored_at": "2026-10-08T12:00:00+00:00"})
    loop = AgentLoop(adapter=None, engine=DeterministicMandateEngine(), ledger=ledger, router=FakeRouter(), rails={}, mandates={},
                     balances={}, pending={}, anchor=FiscoBcosAnchor(transports=[FakeTransport(fail=httpx.ConnectError("refused"))]))

    status = loop.anchor_status()

    assert status["kind"] == "fisco"
    assert status["verified"] is False and "FiscoAnchorError" in status["error"]


@pytest.mark.skipif(not _node_answers(), reason="No FISCO BCOS node answers at FISCO_RPC_URL.")
def test_a_real_node_never_lets_a_head_be_anchored_twice():
    head = hashlib.sha256(b"twice " + datetime.now(timezone.utc).isoformat().encode()).hexdigest()
    anchor = FiscoBcosAnchor()
    anchor.anchor(head, 1, USER)
    first = anchor.block_number(head)

    with pytest.raises(FiscoAnchorError):
        anchor.anchor(head, 2, USER)
    assert anchor.block_number(head) == first


@pytest.mark.skipif(not _node_answers(), reason="No FISCO BCOS node answers at FISCO_RPC_URL.")
def test_a_real_node_lets_no_other_account_anchor(monkeypatch, tmp_path):
    stranger = tmp_path / "stranger.key"
    stranger.write_text("47" * 32 + "\n")
    monkeypatch.setenv("FISCO_KEY_PATH", str(stranger))
    head = hashlib.sha256(b"stranger " + datetime.now(timezone.utc).isoformat().encode()).hexdigest()

    with pytest.raises(FiscoAnchorError):
        FiscoBcosAnchor().anchor(head, 1, USER)
