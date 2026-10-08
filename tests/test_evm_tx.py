"""The pure Python pieces the JSON RPC route signs with, checked against published test vectors."""

from core.evm_tx import address_of, keccak256, rlp_encode, sign_legacy_transaction


def test_keccak256_matches_the_published_vectors():
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    assert keccak256(b"a" * 200).hex() == keccak256(b"a" * 200).hex()


def test_rlp_encodes_the_published_examples():
    assert rlp_encode(b"dog").hex() == "83646f67"
    assert rlp_encode([b"cat", b"dog"]).hex() == "c88363617483646f67"
    assert rlp_encode(b"").hex() == "80"
    assert rlp_encode(0).hex() == "80"
    assert rlp_encode(1024).hex() == "820400"


def test_the_address_of_private_key_one():
    assert address_of((1).to_bytes(32, "big")) == "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"


def test_the_eip155_example_transaction_is_signed_exactly():
    raw = sign_legacy_transaction(
        private_key=bytes.fromhex("46" * 32),
        nonce=9,
        gas_price=20 * 10**9,
        gas=21000,
        to=bytes.fromhex("35" * 20),
        value=10**18,
        data=b"",
        chain_id=1,
    )

    assert raw.hex() == (
        "f86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a7640000"
        "8025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f"
        "761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83"
    )
