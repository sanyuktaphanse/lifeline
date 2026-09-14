from datetime import timedelta

from contracts.schemas import LedgerEntry
from core.ledger import GENESIS_PREV_HASH, HashChainLedger, _hash_of


def test_two_appends_link_into_a_chain():
    ledger = HashChainLedger()

    first = ledger.append("student_001", "decision", {"rule_ids": []})
    second = ledger.append("student_001", "transfer", {"amount": "1200"})

    assert first.seq == 1
    assert second.seq == 2
    assert first.prev_hash == GENESIS_PREV_HASH
    assert second.prev_hash == first.hash
    assert ledger.verify() is None


def test_editing_the_second_entry_breaks_the_chain_at_two():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})
    ledger.append("student_001", "transfer", {"amount": "1200"})
    ledger.append("student_001", "decision", {"rule_ids": []})

    ledger.entries[1].payload["amount"] = "9999"

    assert ledger.verify() == 2


def test_recomputing_the_forged_hash_only_moves_the_break_downstream():
    ledger = HashChainLedger()
    ledger.append("student_001", "decision", {"rule_ids": []})
    ledger.append("student_001", "transfer", {"amount": "1200"})
    ledger.append("student_001", "decision", {"rule_ids": []})

    ledger.entries[1].payload["amount"] = "9999"
    ledger.entries[1].hash = _hash_of(ledger.entries[1])

    assert ledger.verify() == 3


def test_entries_are_the_contract_ledger_entry_with_a_utc_ts():
    ledger = HashChainLedger()

    entry = ledger.append("student_001", "decision", {"rule_ids": []})

    assert type(entry) is LedgerEntry
    assert entry.ts.utcoffset() == timedelta(0)
