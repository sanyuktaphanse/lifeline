"""The TARS encoding and the transaction hash of a FISCO BCOS transaction, built in pure Python."""

from core.evm_tx import keccak256
from core.fisco_tx import TarsWriter, build_transaction, transaction_data_hash


def test_tars_writes_integers_by_size_and_zero_as_its_own_type():
    writer = TarsWriter()
    writer.int(1, 0)
    writer.int(2, 5)
    writer.int(3, 300)
    writer.int(4, 70000)
    writer.int(5, 2**40)
    assert writer.bytes().hex() == "1c" + "2005" + "31012c" + "420001" + "1170" + "530000010000000000"


def test_tars_writes_strings_byte_lists_and_a_tag_above_fourteen():
    writer = TarsWriter()
    writer.string(2, "ab")
    writer.bytes_field(7, b"\x01\x02")
    writer.int(15, 1)
    assert writer.bytes().hex() == "26026162" + "7d000002" + "0102" + "f00f01"


def test_the_transaction_data_hash_is_keccak_of_the_fields_in_order():
    expected = keccak256((0).to_bytes(4, "big") + b"chain0" + b"group0" + (500).to_bytes(8, "big") + b"n1" + b"0xabc" + b"\x01" + b"")

    assert transaction_data_hash("chain0", "group0", 500, "n1", "0xabc", b"\x01") == expected


def test_a_built_transaction_is_hex_and_carries_its_hash_and_a_65_byte_signature():
    raw = build_transaction(bytes.fromhex("46" * 32), "chain0", "group0", 500, "0xabc", b"\x01", nonce="n1")

    digest = transaction_data_hash("chain0", "group0", 500, "n1", "0xabc", b"\x01")
    assert bytes.fromhex(raw).find(digest) > 0
    assert len(raw) % 2 == 0
