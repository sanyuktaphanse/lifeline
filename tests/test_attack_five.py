"""Attack five: the optional FISCO BCOS anchor. Each test states a property the code or its docs claim and
fails while that property does not hold. None of them needs a network: each fakes the node's HTTP layer,
runs a local socket, or reads the contract source, so they behave the same with or without docker."""

import hashlib
import secrets
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from core.agent import AgentLoop
from core.anchor_fisco import ChainTransport, FiscoBcosAnchor, JsonRpcTransport, _word
from core.evm_tx import address_of
from core.ledger import HashChainLedger
from core.mandate import DeterministicMandateEngine
from rails.fake_router import FakeRouter

USER_ID = "student_001"
USER_HASH = hashlib.sha256(USER_ID.encode()).hexdigest()
NODE_URL = "http://127.0.0.1:20200"


def _hex_key(tmp_path: Path) -> Path:
    path = tmp_path / "anchor.key"
    path.write_text(secrets.token_hex(32) + "\n")
    return path


def _loop(ledger: HashChainLedger, anchor, clock=None) -> AgentLoop:
    kwargs = {"clock": clock} if clock is not None else {}
    return AgentLoop(adapter=None, engine=DeterministicMandateEngine(), ledger=ledger, router=FakeRouter(), rails={},
                     mandates={}, balances={}, pending={}, anchor=anchor, **kwargs)


# B1. A node that answers slowly, one byte at a time, holds the anchor, and so the payment's reply, far past
# the five second timeout the module claims, because httpx's timeout is per read, not for the whole call.


def _trickle_server(stop: threading.Event) -> int:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    server.settimeout(0.2)

    def serve() -> None:
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                continue
            conn.recv(65536)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n")
            while not stop.is_set():
                try:
                    conn.sendall(b" ")
                except OSError:
                    break
                time.sleep(1)
            conn.close()
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1]


def test_a_node_that_trickles_its_answer_cannot_hold_an_anchor_past_a_few_seconds(monkeypatch, tmp_path):
    stop = threading.Event()
    port = _trickle_server(stop)
    monkeypatch.setenv("FISCO_RPC_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", str(_hex_key(tmp_path)))
    outcome: list[object] = []

    def run() -> None:
        try:
            outcome.append(FiscoBcosAnchor().anchor(hashlib.sha256(b"head").hexdigest(), 1, USER_HASH))
        except Exception as error:  # the anchor's own error is the expected fast outcome
            outcome.append(error)

    worker = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    worker.start()
    worker.join(12)
    elapsed = time.monotonic() - started
    stop.set()
    worker.join(5)

    assert elapsed < 12 and outcome, f"the anchor was still waiting on the node after {elapsed:.0f} seconds"


# B2. A failing anchor is retried on every call and every tick once the hour has passed, not hourly: the
# anchor_failed note is itself a new entry, so the head is always ahead of the anchored sequence again.


class Failing(ChainTransport):
    def __init__(self) -> None:
        self.attempts = 0

    def send_anchor(self, config, head_hash, seq, user_hash):
        self.attempts += 1
        raise httpx.ConnectTimeout("timed out")

    def read_record(self, config, head_hash):
        raise httpx.ConnectTimeout("timed out")


def test_a_chain_that_stays_down_is_tried_at_most_once_an_hour(monkeypatch):
    monkeypatch.setenv("FISCO_RPC_URL", "http://10.255.255.1:20200")
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", "/nonexistent/anchor.key")
    ledger = HashChainLedger()
    ledger.append("agent", "turn", {"user_id": USER_ID, "turn": 1})
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    transport = Failing()
    loop = _loop(ledger, FiscoBcosAnchor(transports=[transport]), clock=lambda: later)

    # What the API's tick does once a minute for each student, and what every public call does after it.
    for _ in range(3):
        loop._anchor_if_due(USER_ID)

    notes = [entry for entry in ledger.entries() if entry.payload.get("kind") == "anchor_failed"]
    assert transport.attempts == 1 and len(notes) == 1, f"{transport.attempts} attempts and {len(notes)} notes in one minute"


# B3. The verify endpoint and verify_ledger read the chain three times in a row, under the API's one lock,
# so a slow node costs three timeouts (fifteen seconds) during which no payment can be confirmed.


def _record_output(head: str, sender: bytes = b"") -> str:
    # The anchor entry names head_seq 1, and the record names the same sequence and, since the brief's fix,
    # Lifeline's own address as its sender.
    words = [bytes.fromhex(head), _word(1), bytes.fromhex(USER_HASH), _word(1_760_000_000), _word(sender), _word(3)]
    return "0x" + b"".join(words).hex()


def test_anchor_status_reads_the_chain_once(monkeypatch, tmp_path):
    key = _hex_key(tmp_path)
    monkeypatch.setenv("FISCO_RPC_URL", NODE_URL)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", str(key))
    ours = bytes.fromhex(address_of(bytes.fromhex(key.read_text().strip()))[2:])
    ledger = HashChainLedger()
    head = ledger.append("agent", "turn", {"user_id": USER_ID, "turn": 1})
    ledger.append("agent", "anchor", {"user_id": USER_ID, "head_hash": head.hash, "head_seq": head.seq,
                                      "anchor_id": "fisco:0x1", "anchored_at": "2026-10-08T12:00:00+00:00"})
    calls = []

    def post(url, payload, timeout):
        calls.append(payload["method"])
        return {"result": {"status": 0, "output": _record_output(head.hash, ours)}}

    status = _loop(ledger, FiscoBcosAnchor(transports=[JsonRpcTransport(post=post)])).anchor_status()

    assert status["verified"] is True
    assert len(calls) == 1, f"anchor_status made {len(calls)} chain reads, each up to five seconds under the lock"


# A1. A key file holding the raw 32 bytes, a realistic mistake, puts a byte of the key in the anchor's error,
# which the loop writes verbatim into the anchor_failed note in the ledger.


def test_a_binary_key_file_leaks_no_key_byte_into_the_error(monkeypatch, tmp_path):
    key = bytes([0x9C]) + secrets.token_bytes(31)
    path = tmp_path / "anchor.key"
    path.write_bytes(key)
    monkeypatch.setenv("FISCO_RPC_URL", NODE_URL)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", str(path))

    def post(url, payload, timeout):
        return {"result": 1}

    with pytest.raises(Exception) as raised:
        FiscoBcosAnchor(transports=[JsonRpcTransport(post=post)]).anchor(hashlib.sha256(b"h").hexdigest(), 1, USER_HASH)

    assert "0x9c" not in str(raised.value), str(raised.value)


# A2. The user hash on the chain is an unsalted SHA 256 of the user id, so anyone who reads the chain recovers
# the id by hashing a guess such as the demo's student_001, and links every anchor of the same student.


class Recording(ChainTransport):
    def __init__(self) -> None:
        self.user_hashes: list[str] = []

    def send_anchor(self, config, head_hash, seq, user_hash):
        self.user_hashes.append(user_hash)
        return "0x" + "ab" * 32

    def read_record(self, config, head_hash):
        return None


def test_the_user_hash_on_the_chain_cannot_be_reversed_by_hashing_a_guessed_id(monkeypatch):
    monkeypatch.setenv("FISCO_RPC_URL", NODE_URL)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", "/unused")
    ledger = HashChainLedger()
    ledger.append("agent", "turn", {"user_id": USER_ID, "turn": 1})
    transport = Recording()
    loop = _loop(ledger, FiscoBcosAnchor(transports=[transport]), clock=lambda: datetime.now(timezone.utc) + timedelta(hours=2))

    loop._anchor_if_due(USER_ID)

    assert transport.user_hashes, "nothing was anchored"
    assert transport.user_hashes[0] != hashlib.sha256(USER_ID.encode()).hexdigest()


# B4. A contract address that is not hexadecimal is sent to the node unchecked. FISCO BCOS v3.16.4 accepts
# the transaction into its pool, then fails every attempt to execute the block holding it (boost non_hex_input
# in the node log), so the whole chain stops producing blocks and every later anchor, by anyone, times out.
# Observed on the local network on this machine: one anchor with FISCO_CONTRACT_ADDRESS=hello left it at
# block 5 with every later transaction pending.


def test_a_contract_address_that_is_not_an_address_is_refused_before_anything_is_sent(monkeypatch, tmp_path):
    monkeypatch.setenv("FISCO_RPC_URL", NODE_URL)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "hello")
    monkeypatch.setenv("FISCO_KEY_PATH", str(_hex_key(tmp_path)))
    sent = []

    def post(url, payload, timeout):
        sent.append(payload["method"])
        if payload["method"] == "getBlockNumber":
            return {"result": 5}
        return {"result": {"status": 0, "transactionHash": "0x" + "ab" * 32}}

    try:
        FiscoBcosAnchor(transports=[JsonRpcTransport(post=post)]).anchor(hashlib.sha256(b"h").hexdigest(), 1, USER_HASH)
    except Exception:  # refusing the address is the expected outcome
        pass

    assert "sendTransaction" not in sent


# C1. verify accepts a record for the head whoever wrote it. The contract lets any account anchor any head,
# so whoever can rewrite and rechain the ledger file, which holds no secret, anchors the rewritten head from a
# fresh key and the verify endpoint reports it verified. The local anchor's HMAC secret prevents exactly this.


def test_a_record_written_by_another_account_does_not_verify(monkeypatch, tmp_path):
    key = _hex_key(tmp_path)
    monkeypatch.setenv("FISCO_RPC_URL", NODE_URL)
    monkeypatch.setenv("FISCO_CONTRACT_ADDRESS", "0x" + "12" * 20)
    monkeypatch.setenv("FISCO_KEY_PATH", str(key))
    ledger = HashChainLedger()
    tampered = ledger.append("agent", "turn", {"user_id": USER_ID, "turn": 1, "rewritten": True})
    ledger.append("agent", "anchor", {"user_id": USER_ID, "head_hash": tampered.hash, "head_seq": tampered.seq,
                                      "anchor_id": "fisco:0xforged", "anchored_at": "2026-10-08T12:00:00+00:00"})
    stranger = "ee" * 20
    assert "0x" + stranger != address_of(bytes.fromhex(key.read_text().strip()))
    words = [bytes.fromhex(tampered.hash), _word(999), bytes.fromhex(USER_HASH), _word(1_760_000_000),
             _word(bytes.fromhex(stranger)), _word(7)]

    def post(url, payload, timeout):
        return {"result": {"status": 0, "output": "0x" + b"".join(words).hex()}}

    status = _loop(ledger, FiscoBcosAnchor(transports=[JsonRpcTransport(post=post)])).anchor_status()

    assert status["verified"] is False, "a head another account anchored, with a sequence of its choosing, verified"


# C2. The contract overwrites a head's record on every call, from any account, so the evidence of when a head
# first existed can be replaced by a later block, time and sender.


def test_the_contract_never_overwrites_a_record_or_takes_one_from_another_account():
    source = (Path(__file__).resolve().parent.parent / "chain" / "LifelineEvidence.sol").read_text()
    body = source.split("function anchor(", 1)[1].split("function verify(", 1)[0]

    assert "require(" in body, "anchor() has no guard: any account overwrites any head's record"


