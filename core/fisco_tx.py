"""A FISCO BCOS 3.x transaction, built and signed in pure Python for the anchor's JSON RPC route.

The node's native sendTransaction takes the transaction TARS encoded. The schema is bcostars.Transaction
in bcos-tars-protocol/tars/Transaction.tars of FISCO BCOS v3.16.4, and the hash of version 0 transaction
data is Keccak 256 over its fields in order, as bcos-tars-protocol/impl/TarsHashable.h computes it. The
signature is r, s and the recovery byte. Source: docs/decisions.md, 8 October 2026.
"""

import secrets

from core.evm_tx import _sign, keccak256

# TARS head types.
_INT1, _INT2, _INT4, _INT8, _STRING1, _STRING4, _STRUCT_BEGIN, _STRUCT_END, _ZERO, _SIMPLE_LIST = 0, 1, 2, 3, 6, 7, 10, 11, 12, 13
# Transaction attribute for a contract called through the Solidity ABI.
EVM_ABI_CODEC = 1


class TarsWriter:
    def __init__(self) -> None:
        self._out = bytearray()

    def _head(self, tag: int, kind: int) -> None:
        if tag < 15:
            self._out.append((tag << 4) | kind)
        else:
            self._out += bytes([0xF0 | kind, tag])

    def int(self, tag: int, value: int) -> None:
        if value == 0:
            self._head(tag, _ZERO)
        elif -128 <= value <= 127:
            self._head(tag, _INT1)
            self._out += value.to_bytes(1, "big", signed=True)
        elif -32768 <= value <= 32767:
            self._head(tag, _INT2)
            self._out += value.to_bytes(2, "big", signed=True)
        elif -(2**31) <= value < 2**31:
            self._head(tag, _INT4)
            self._out += value.to_bytes(4, "big", signed=True)
        else:
            self._head(tag, _INT8)
            self._out += value.to_bytes(8, "big", signed=True)

    def string(self, tag: int, value: str) -> None:
        data = value.encode("utf-8")
        if len(data) <= 255:
            self._head(tag, _STRING1)
            self._out.append(len(data))
        else:
            self._head(tag, _STRING4)
            self._out += len(data).to_bytes(4, "big")
        self._out += data

    def bytes_field(self, tag: int, value: bytes) -> None:
        """A vector<byte>, written as TARS's simple list: the head, a byte element head, the length, the bytes."""
        self._head(tag, _SIMPLE_LIST)
        self._head(0, _INT1)
        self.int(0, len(value))
        self._out += value

    def struct(self, tag: int, inner: "TarsWriter") -> None:
        self._head(tag, _STRUCT_BEGIN)
        self._out += inner.bytes()
        self._head(0, _STRUCT_END)

    def bytes(self) -> bytes:
        return bytes(self._out)


def transaction_data_hash(chain_id: str, group_id: str, block_limit: int, nonce: str, to: str, data: bytes, abi: str = "") -> bytes:
    """Keccak 256 over the fields of version 0 transaction data, in the order the node hashes them."""
    return keccak256(
        (0).to_bytes(4, "big")
        + chain_id.encode()
        + group_id.encode()
        + block_limit.to_bytes(8, "big", signed=True)
        + nonce.encode()
        + to.encode()
        + data
        + abi.encode()
    )


def build_transaction(
    private_key: bytes, chain_id: str, group_id: str, block_limit: int, to: str, data: bytes, nonce: str | None = None
) -> str:
    """The hex of a signed, TARS encoded transaction for the node's sendTransaction. `to` is empty to deploy."""
    nonce = nonce or str(secrets.randbits(128))
    digest = transaction_data_hash(chain_id, group_id, block_limit, nonce, to, data)
    r, s, parity = _sign(private_key, digest)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([parity])
    fields = TarsWriter()
    fields.int(1, 0)
    fields.string(2, chain_id)
    fields.string(3, group_id)
    fields.int(4, block_limit)
    fields.string(5, nonce)
    fields.string(6, to)
    fields.bytes_field(7, data)
    transaction = TarsWriter()
    transaction.struct(1, fields)
    transaction.bytes_field(2, digest)
    transaction.bytes_field(3, signature)
    transaction.int(4, 0)
    transaction.int(5, EVM_ABI_CODEC)
    return transaction.bytes().hex()
