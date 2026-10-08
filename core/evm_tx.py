"""What the FISCO BCOS anchor's JSON RPC route needs to send a signed transaction, in pure Python.

Keccak 256, RLP and secp256k1 signing with deterministic nonces (RFC 6979) and EIP-155 replay
protection, written here so the optional chain anchor adds no dependency. Each piece is checked against
published test vectors in tests/test_evm_tx.py. Source: docs/decisions.md, 8 October 2026.
"""

import hashlib
import hmac

# Keccak-f[1600] round constants and rotation offsets, from the Keccak reference.
_ROUND_CONSTANTS = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROTATIONS = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1
_RATE = 136  # bytes, for a 256 bit output


def _rotate(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (64 - shift))) & _MASK if shift else value


def _keccak_f(state: list[list[int]]) -> None:
    for constant in _ROUND_CONSTANTS:
        c = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotate(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x][y] ^= d[x]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rotate(state[x][y], _ROTATIONS[x][y])
        for x in range(5):
            for y in range(5):
                state[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y])
        state[0][0] ^= constant


def keccak256(data: bytes) -> bytes:
    """Keccak 256 as Ethereum uses it: the original padding, not SHA3-256's."""
    padded = bytearray(data) + b"\x01"
    padded += b"\x00" * (-len(padded) % _RATE)
    padded[-1] |= 0x80
    state = [[0] * 5 for _ in range(5)]
    for offset in range(0, len(padded), _RATE):
        block = padded[offset : offset + _RATE]
        for index in range(_RATE // 8):
            x, y = index % 5, index // 5
            state[x][y] ^= int.from_bytes(block[index * 8 : index * 8 + 8], "little")
        _keccak_f(state)
    return b"".join(state[index % 5][index // 5].to_bytes(8, "little") for index in range(4))


def _rlp_bytes(value: int | bytes) -> bytes:
    if isinstance(value, int):
        return value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    return value


def _rlp_length(length: int, offset: int) -> bytes:
    if length < 56:
        return bytes([offset + length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([offset + 55 + len(encoded)]) + encoded


def rlp_encode(item: int | bytes | list) -> bytes:
    if isinstance(item, list):
        payload = b"".join(rlp_encode(element) for element in item)
        return _rlp_length(len(payload), 0xC0) + payload
    data = _rlp_bytes(item)
    if len(data) == 1 and data[0] < 0x80:
        return data
    return _rlp_length(len(data), 0x80) + data


# secp256k1, from SEC 2.
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _add(a: tuple[int, int] | None, b: tuple[int, int] | None) -> tuple[int, int] | None:
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % _P == 0:
        return None
    if a == b:
        slope = 3 * a[0] * a[0] * pow(2 * a[1], -1, _P) % _P
    else:
        slope = (b[1] - a[1]) * pow(b[0] - a[0], -1, _P) % _P
    x = (slope * slope - a[0] - b[0]) % _P
    return x, (slope * (a[0] - x) - a[1]) % _P


def _multiply(k: int, point: tuple[int, int] = _G) -> tuple[int, int]:
    result: tuple[int, int] | None = None
    addend: tuple[int, int] | None = point
    while k:
        if k & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        k >>= 1
    assert result is not None
    return result


def address_of(private_key: bytes) -> str:
    x, y = _multiply(int.from_bytes(private_key, "big"))
    return "0x" + keccak256(x.to_bytes(32, "big") + y.to_bytes(32, "big"))[-20:].hex()


def _nonce(private_key: int, digest: bytes) -> int:
    """The deterministic signing nonce of RFC 6979, section 3.2, with HMAC SHA 256."""
    key = private_key.to_bytes(32, "big")
    message = (int.from_bytes(digest, "big") % _N).to_bytes(32, "big")
    v, k = b"\x01" * 32, b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + key + message, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + key + message, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        candidate = int.from_bytes(v, "big")
        if 1 <= candidate < _N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def _sign(private_key: bytes, digest: bytes) -> tuple[int, int, int]:
    """r, s and the recovery parity of an ECDSA signature, with s in the lower half as Ethereum requires."""
    secret = int.from_bytes(private_key, "big")
    k = _nonce(secret, digest)
    x, y = _multiply(k)
    r = x % _N
    s = pow(k, -1, _N) * (int.from_bytes(digest, "big") + r * secret) % _N
    parity = y & 1
    if s > _N // 2:
        s, parity = _N - s, parity ^ 1
    return r, s, parity


def sign_legacy_transaction(
    private_key: bytes, nonce: int, gas_price: int, gas: int, to: bytes, value: int, data: bytes, chain_id: int
) -> bytes:
    """A legacy transaction signed with EIP-155 replay protection, ready for eth_sendRawTransaction.

    `to` is empty for a contract deployment.
    """
    fields = [nonce, gas_price, gas, to, value, data]
    digest = keccak256(rlp_encode([*fields, chain_id, 0, 0]))
    r, s, parity = _sign(private_key, digest)
    return rlp_encode([*fields, chain_id * 2 + 35 + parity, r, s])
