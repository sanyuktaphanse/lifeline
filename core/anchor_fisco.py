"""The FISCO BCOS anchor: the ledger head written to a LifelineEvidence contract on a FISCO BCOS chain.

It implements the same Anchor interface as the local signed anchor and is chosen only when ANCHOR is
fisco; the product works the same without it. Only the head hash, its sequence number and a SHA 256 hash
of the user id reach the chain, never an amount, a payee or a user id. The configuration and the key
path are read on every call, and the key is never logged or put in a message.
Source: docs/decisions.md, 8 October 2026.

The client tries the project's Python SDK first and JSON RPC second, each behind a small transport
adapter, so a test can fake either without a network.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from contracts.interfaces import Anchor
from core.anchor_local import DIGEST, FISCO, AnchorNotConfigured, _is_seq
from core.model_adapter import environment

CONFIG_VARS = ("FISCO_RPC_URL", "FISCO_CONTRACT_ADDRESS", "FISCO_KEY_PATH")
# Source: this module. An anchor runs right after a payment in the same request, so a chain that does not
# answer must fail fast and leave a note, never hold the payment's reply. Not a money rule.
TIMEOUT_SECONDS = 5.0


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
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


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


class JsonRpcTransport(ChainTransport):
    """The node's JSON RPC, posted through an adapter so a test can fake the HTTP layer."""

    def __init__(self, post: Post = _post) -> None:
        self._post = post

    def _rpc(self, config: FiscoConfig, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        reply = self._post(config.rpc_url, payload, TIMEOUT_SECONDS)
        if "error" in reply:
            raise RuntimeError(f"The node answered {method} with an error: {reply['error']}")
        return reply.get("result")

    def send_anchor(self, config: FiscoConfig, head_hash: str, seq: int, user_hash: str) -> str:
        raise TransportUnavailable("The JSON RPC route cannot sign a FISCO BCOS transaction in this version.")

    def read_record(self, config: FiscoConfig, head_hash: str) -> ChainRecord | None:
        self._rpc(config, "call", [config.contract_address, head_hash])
        raise TransportUnavailable("The JSON RPC route cannot decode a FISCO BCOS call result in this version.")


def default_transports() -> list[ChainTransport]:
    return [PythonSdkTransport(), JsonRpcTransport()]


def _config() -> FiscoConfig:
    """The three settings, read on every call; a missing one is named, its value never."""
    env = environment(None)
    values = {name: env.get(name, "").strip() for name in CONFIG_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise AnchorNotConfigured(f"ANCHOR is fisco and {', '.join(missing)} is not set, so nothing was anchored on the chain.")
    return FiscoConfig(*(values[name] for name in CONFIG_VARS))


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
                raise FiscoAnchorError(f"{type(error).__name__}: {error}") from None
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

    def _record(self, head_hash: str) -> ChainRecord | None:
        record = self._through(lambda transport, config: transport.read_record(config, head_hash))
        return record if record is not None and record.head_hash == head_hash else None

    def verify(self, head_hash: str) -> bool:
        return self._record(head_hash) is not None

    def anchored_at(self, head_hash: str) -> datetime | None:
        """The block time the contract recorded for the head, or None when it holds none."""
        record = self._record(head_hash)
        return None if record is None else record.timestamp.astimezone(timezone.utc)

    def block_number(self, head_hash: str) -> int | None:
        """The block the head was anchored in, for the verify endpoint, or None when it holds none."""
        record = self._record(head_hash)
        return None if record is None else record.block_number
