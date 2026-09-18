from datetime import timedelta

from contracts.interfaces import Ledger
from contracts.schemas import LedgerEntry
from core.ledger import GENESIS_PREV_HASH, HashChainLedger, _hash_of


def test_hash_chain_ledger_implements_the_ledger_interface():
    assert isinstance(HashChainLedger(), Ledger)


def test_two_appends_link_into_a_chain():
    ledger = HashChainLedger()

    first = ledger.append("student_001", "decision", {"rule_ids": []})
    second = ledger.append("student_001", "transfer", {"amount": "1200"})

    assert first.seq == 1
    assert second.seq == 2
    assert first.prev_hash == GENESIS_PREV_HASH
    assert second.prev_hash == first.hash
    assert ledger.verify() is None


def test_head_of_an_empty_ledger_is_the_genesis_hash():
    assert HashChainLedger().head() == "0" * 64


def test_head_is_the_hash_of_the_last_entry():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})
    last = ledger.append("student_001", "transfer", {"amount": "1200"})

    assert ledger.head() == last.hash


def test_entries_returns_a_copy_of_the_list():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})

    entries = ledger.entries()
    entries.clear()

    assert [entry.seq for entry in ledger.entries()] == [1]
    assert ledger.entries() is not ledger.entries()


def test_mutating_a_returned_entry_does_not_change_the_chain():
    ledger = HashChainLedger()
    ledger.append("student_001", "transfer", {"amount": "1200"})
    ledger.append("student_001", "decision", {"rule_ids": []})

    returned = ledger.entries()[0]
    returned.payload["amount"] = "9999"
    returned.hash = "f" * 64

    assert ledger.verify() is None
    assert ledger.entries()[0].payload["amount"] == "1200"


def test_editing_the_second_entry_breaks_the_chain_at_two():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})
    ledger.append("student_001", "transfer", {"amount": "1200"})
    ledger.append("student_001", "decision", {"rule_ids": []})

    ledger._entries[1].payload["amount"] = "9999"

    assert ledger.verify() == 2


def test_recomputing_the_forged_hash_only_moves_the_break_downstream():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})
    ledger.append("student_001", "transfer", {"amount": "1200"})
    ledger.append("student_001", "decision", {"rule_ids": []})

    ledger._entries[1].payload["amount"] = "9999"
    ledger._entries[1].hash = _hash_of(ledger._entries[1])

    assert ledger.verify() == 3


def test_entries_are_the_contract_ledger_entry_with_a_utc_ts():
    ledger = HashChainLedger()

    entry = ledger.append("student_001", "decision", {"rule_ids": []})

    assert type(entry) is LedgerEntry
    assert entry.ts.utcoffset() == timedelta(0)


def test_a_file_ledger_writes_one_json_line_per_entry_and_reloads_an_intact_chain(tmp_path):
    from core.ledger import JsonlLedger

    path = tmp_path / "data" / "ledger.jsonl"
    first = JsonlLedger(path)
    first.append("agent", "proposal", {"user_id": "student_001", "amount": "1200", "nested": {"a": [1, 2.5, None]}})
    first.append("agent", "decision", {"user_id": "student_001", "rule_ids": ["R11"]})

    reloaded = JsonlLedger(path)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert reloaded.entries() == first.entries()
    assert reloaded.verify() is None
    third = reloaded.append("agent", "note", {"user_id": "student_001"})
    assert third.seq == 3
    assert third.prev_hash == first.head()
    assert JsonlLedger(path).verify() is None


def test_a_tampered_file_ledger_loads_and_verify_names_the_first_broken_entry(tmp_path):
    from core.ledger import JsonlLedger

    path = tmp_path / "ledger.jsonl"
    ledger = JsonlLedger(path)
    ledger.append("agent", "proposal", {"amount": "1200"})
    ledger.append("agent", "decision", {"rule_ids": ["R11"]})
    path.write_text(path.read_text(encoding="utf-8").replace('"1200"', '"9999"'), encoding="utf-8")

    assert JsonlLedger(path).verify() == 1


def test_a_missing_file_is_an_empty_ledger(tmp_path):
    from core.ledger import JsonlLedger

    ledger = JsonlLedger(tmp_path / "none" / "ledger.jsonl")

    assert ledger.entries() == []
    assert not (tmp_path / "none" / "ledger.jsonl").exists()
