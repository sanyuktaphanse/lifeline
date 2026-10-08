"""The FISCO BCOS anchor: the ledger head written to a LifelineEvidence contract on a FISCO BCOS chain.

It implements the same Anchor interface as the local signed anchor and is chosen only when ANCHOR is
fisco; the product works the same without it. Only the head hash, its sequence number and a SHA 256 hash
of the user id reach the chain, never an amount, a payee or a user id. The configuration and the key
path are read on every call, and the key is never logged or put in a message.
Source: docs/decisions.md, 8 October 2026.

The client tries the project's Python SDK first and JSON RPC second, each behind a small transport
adapter, so a test can fake either without a network.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from contracts.interfaces import Anchor
from core.anchor_local import DIGEST, FISCO, AnchorNotConfigured, _is_seq
from core.evm_tx import address_of, keccak256
from core.fisco_tx import build_transaction
from core.model_adapter import environment

CONFIG_VARS = ("FISCO_RPC_URL", "FISCO_CONTRACT_ADDRESS", "FISCO_KEY_PATH")
# Source: this module. An anchor runs right after a payment in the same request, so a chain that does not
# answer must fail fast and leave a note, never hold the payment's reply. Not a money rule.
TIMEOUT_SECONDS = 5.0
# Source: this module. The largest answer a node may give one request, so a node cannot fill memory.
MAX_ANSWER_BYTES = 1_000_000
# Source: this module. The longest piece of a node's words kept in an error, which reaches the ledger.
MAX_ERROR_CHARS = 300
CONTRACT_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
TRANSACTION_HASH = re.compile(r"0x[0-9a-fA-F]{64}")
# A URL's user and password, which an error must never carry.
URL_CREDENTIALS = re.compile(r"//[^/@\s]+@")
# The group and chain build_chain.sh creates by default. Source: chain/nodes/127.0.0.1/node0/config.genesis.
GROUP_ID = "group0"
CHAIN_ID = "chain0"
# Source: this module. How many blocks ahead a transaction stays valid; the node refuses one too far ahead.
BLOCK_LIMIT_AHEAD = 500
ANCHOR_SELECTOR = keccak256(b"anchor(bytes32,uint64,bytes32)")[:4]
VERIFY_SELECTOR = keccak256(b"verify(bytes32)")[:4]
# FISCO BCOS records block time in milliseconds; a value this large cannot be seconds.
MILLISECONDS_FROM = 10**12


class FiscoAnchorError(RuntimeError):
    """The chain could not anchor or read a head. The loop turns it into an anchor_failed note."""


class TransportUnavailable(RuntimeError):
    """This route to the chain cannot be used here, such as an SDK that is not installed."""


@dataclass(frozen=True)
class FiscoConfig:
    rpc_url: str
    contract_address: str
    key_path: str


@dataclass(frozen=True)
class ChainRecord:
    """What the contract stores for a head: the head, its sequence, the user hash, the block time, the sender."""

    head_hash: str
    seq: int
    user_hash: str
    timestamp: datetime
    sender: str
    block_number: int | None


class ChainTransport(ABC):
    """One way of reaching the chain. A test fakes it; the anchor never talks to the network directly."""

    @abstractmethod
    def send_anchor(self, config: FiscoConfig, head_hash: str, seq: int, user_hash: str) -> str:
        """Send anchor(head, seq, userHash) and return the transaction hash once it is confirmed."""

    @abstractmethod
    def read_record(self, config: FiscoConfig, head_hash: str) -> ChainRecord | None:
        """Call verify(head) and return the record, or None when the contract holds zeros."""


Post = Callable[[str, dict[str, Any], float], dict[str, Any]]


def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """One JSON RPC request with an overall deadline, not only one per read, so a node that answers a byte
    at a time cannot hold the payment's reply, and a size cap. Proxy settings are not followed."""
    deadline = time.monotonic() + timeout
    body = bytearray()
    with httpx.Client(timeout=timeout, trust_env=False) as client, client.stream("POST", url, json=payload) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            body += chunk
            if time.monotonic() > deadline:
                raise httpx.ReadTimeout("The node did not finish answering within the deadline.")
            if len(body) > MAX_ANSWER_BYTES:
                raise ValueError("The node's answer is larger than an answer can be.")
    answer = json.loads(body)
    if not isinstance(answer, dict):
        raise ValueError("The node's answer is not a JSON object.")
    return answer


class PythonSdkTransport(ChainTransport):
    """The FISCO BCOS Python SDK, when it is installed. It is not on PyPI, so it is usually unavailable."""

    def _client(self) -> Any:
        try:
            from bcos3sdk.bcos3client import Bcos3Client  # type: ignore[import-not-found]
        except ImportError as error:
            raise TransportUnavailable("The FISCO BCOS Python SDK (bcos3sdk) is not installed.") from error
        return Bcos3Client

    def send_anchor(self, config: FiscoConfig, head_hash: str, seq: int, user_hash: str) -> str:
        self._client()
        raise TransportUnavailable("The FISCO BCOS Python SDK route is not wired in this version.")

    def read_record(self, config: FiscoConfig, head_hash: str) -> ChainRecord | None:
        self._client()
        raise TransportUnavailable("The FISCO BCOS Python SDK route is not wired in this version.")


def _private_key(path: str) -> bytes:
    """The anchor key, read from its file on every call: 64 hexadecimal characters, nothing else kept."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read(256)
    except OSError as error:
        raise AnchorNotConfigured(f"FISCO_KEY_PATH names a file that cannot be read: {type(error).__name__}.") from None
    try:
        text = raw.decode("ascii").strip()
    except UnicodeDecodeError:
        # The message is fixed, so no byte of a key written as raw bytes reaches an error or the ledger.
        raise AnchorNotConfigured("FISCO_KEY_PATH must name a file holding one private key as 64 hexadecimal characters.") from None
    text = text[2:] if text.startswith("0x") else text
    if len(text) != 64 or any(char not in "0123456789abcdefABCDEF" for char in text):
        raise AnchorNotConfigured("FISCO_KEY_PATH must name a file holding one private key as 64 hexadecimal characters.")
    return bytes.fromhex(text)


def _word(value: int | bytes) -> bytes:
    return value.rjust(32, b"\x00") if isinstance(value, bytes) else value.to_bytes(32, "big")


class JsonRpcTransport(ChainTransport):
    """The node's native JSON RPC, posted through an adapter so a test can fake the HTTP layer.

    A transaction is built, TARS encoded and signed here in pure Python (core/fisco_tx.py) and sent with
    sendTransaction, which answers with the receipt once the transaction is in a block. The node's web3
    route refuses any sender with no balance, and Lifeline's account holds none, so it is not used.
    """

    def __init__(self, post: Post = _post) -> None:
        self._post = post

    def _rpc(self, config: FiscoConfig, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        reply = self._post(config.rpc_url, payload, TIMEOUT_SECONDS)
        if "error" in reply:
            raise RuntimeError(f"The node answered {method} with an error: {reply['error']}")
        return reply.get("result")

    def send_raw(self, config: FiscoConfig, private_key: bytes, to: str, data: bytes) -> dict[str, Any]:
        """Sign and send one transaction; the receipt once it is in a block, or an error when it failed."""
        block = int(self._rpc(config, "getBlockNumber", [GROUP_ID, ""]))
        raw = build_transaction(private_key, CHAIN_ID, GROUP_ID, block + BLOCK_LIMIT_AHEAD, to, data)
        receipt = self._rpc(config, "sendTransaction", [GROUP_ID, "", raw, False])
        if not isinstance(receipt, dict) or str(receipt.get("status", "")) != "0":
            status = str(receipt.get("status"))[:20] if isinstance(receipt, dict) else "missing"
            raise RuntimeError(f"The transaction was not executed: status {status}.")
        return receipt

    def send_anchor(self, config: FiscoConfig, head_hash: str, seq: int, user_hash: str) -> str:
        data = ANCHOR_SELECTOR + bytes.fromhex(head_hash) + _word(seq) + bytes.fromhex(user_hash)
        receipt = self.send_raw(config, _private_key(config.key_path), config.contract_address, data)
        transaction = str(receipt.get("transactionHash", ""))
        if not TRANSACTION_HASH.fullmatch(transaction):
            raise ValueError("The node's receipt carries no well formed transaction hash.")
        return transaction

    def read_record(self, config: FiscoConfig, head_hash: str) -> ChainRecord | None:
        data = "0x" + (VERIFY_SELECTOR + bytes.fromhex(head_hash)).hex()
        answer = self._rpc(config, "call", [GROUP_ID, "", config.contract_address, data])
        if not isinstance(answer, dict) or str(answer.get("status", "")) != "0":
            status = str(answer.get("status"))[:20] if isinstance(answer, dict) else "missing"
            raise RuntimeError(f"The call to verify was not executed: status {status}.")
        result = bytes.fromhex(str(answer.get("output", "")).removeprefix("0x"))
        if len(result) < 192:
            raise ValueError(f"verify returned {len(result)} bytes, not the six words of a record.")
        words = [result[index : index + 32] for index in range(0, 192, 32)]
        if not any(words[0]):
            return None
        stamp = int.from_bytes(words[3], "big")
        seconds = stamp / 1000 if stamp >= MILLISECONDS_FROM else stamp
        return ChainRecord(
            head_hash=words[0].hex(),
            seq=int.from_bytes(words[1], "big"),
            user_hash=words[2].hex(),
            timestamp=datetime.fromtimestamp(seconds, timezone.utc),
            sender="0x" + words[4][-20:].hex(),
            block_number=int.from_bytes(words[5], "big"),
        )


def default_transports() -> list[ChainTransport]:
    return [PythonSdkTransport(), JsonRpcTransport()]


def _config() -> FiscoConfig:
    """The three settings, read on every call; a missing one is named, its value never."""
    env = environment(None)
    values = {name: env.get(name, "").strip() for name in CONFIG_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise AnchorNotConfigured(f"ANCHOR is fisco and {', '.join(missing)} is not set, so nothing was anchored on the chain.")
    if not CONTRACT_ADDRESS.fullmatch(values["FISCO_CONTRACT_ADDRESS"]):
        # A malformed address is refused before anything is sent: one sent to FISCO BCOS v3.16.4 stopped the
        # local chain making blocks. Source: the FISCO anchor attacker brief of 8 October.
        raise AnchorNotConfigured("FISCO_CONTRACT_ADDRESS must be 0x followed by 40 hexadecimal characters.")
    return FiscoConfig(*(values[name] for name in CONFIG_VARS))


def _reported(error: Exception) -> str:
    """An error as the ledger may hold it: its type and the node's words, bounded, with no URL credentials."""
    return URL_CREDENTIALS.sub("//", f"{type(error).__name__}: {error}")[:MAX_ERROR_CHARS]


class FiscoBcosAnchor(Anchor):
    kind = FISCO

    def __init__(self, transports: Sequence[ChainTransport] | None = None) -> None:
        self._transports = list(transports) if transports is not None else default_transports()

    def _through(self, use: Callable[[ChainTransport, FiscoConfig], Any]) -> Any:
        config = _config()
        tried: list[str] = []
        for transport in self._transports:
            try:
                return use(transport, config)
            except TransportUnavailable as unavailable:
                tried.append(str(unavailable))
            except AnchorNotConfigured:
                raise
            except Exception as error:  # anti-pattern: SILENT-EXCEPT ok, every chain failure becomes this anchor's own error, which the loop notes
                # The type and the node's words only; the key is read by the transport and never put here.
                raise FiscoAnchorError(_reported(error)) from None
        raise AnchorNotConfigured("No route to FISCO BCOS works here. Tried: " + " ".join(tried))

    def anchor(self, head_hash: str, seq: int, user_hash: str) -> str:
        if not isinstance(head_hash, str) or not DIGEST.fullmatch(head_hash):
            raise ValueError("An anchor takes a ledger head hash, 64 lowercase hexadecimal characters.")
        if not _is_seq(seq):
            raise ValueError("An anchor takes the head's sequence number, a whole number from zero.")
        if not isinstance(user_hash, str) or not DIGEST.fullmatch(user_hash):
            raise ValueError("An anchor takes a SHA 256 hash of the user id, never the id itself.")
        transaction = self._through(lambda transport, config: transport.send_anchor(config, head_hash, seq, user_hash))
        return f"{FISCO}:{transaction}"

    def record_of(self, head_hash: str) -> ChainRecord | None:
        """The contract's record of the head, in one read, only when Lifeline's own account wrote it.

        A record another account wrote is no evidence, so it reads as none. Source: the FISCO anchor
        attacker brief of 8 October.
        """
        record = self._through(lambda transport, config: transport.read_record(config, head_hash))
        if record is None or record.head_hash != head_hash:
            return None
        ours = address_of(_private_key(_config().key_path))
        return record if record.sender.casefold() == ours.casefold() else None

    def verify(self, head_hash: str) -> bool:
        return self.record_of(head_hash) is not None

    def anchored_at(self, head_hash: str) -> datetime | None:
        """The block time the contract recorded for the head, or None when it holds none."""
        record = self.record_of(head_hash)
        return None if record is None else record.timestamp.astimezone(timezone.utc)

    def block_number(self, head_hash: str) -> int | None:
        """The block the head was anchored in, for the verify endpoint, or None when it holds none."""
        record = self.record_of(head_hash)
        return None if record is None else record.block_number
