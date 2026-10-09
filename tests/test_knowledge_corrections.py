"""The corrections from the knowledge base audit of 9 October 2026, docs/knowledge_audit.md.

Each entry the pass rewrote says only what its page says, in the page's own scope, and records CC as its
first checker with the second check still to come. Source: docs/decisions.md, 9 October 2026.
"""

from datetime import date
from pathlib import Path

import pytest

from rails.fake_router import FakeRouter
from rails.knowledge.loader import load_knowledge
from rails.sim import rules

REWRITTEN = [
    "br_pix_instant_001",
    "cn_fx_quota_001",
    "cn_edu_remit_002",
    "cn_edu_docs_003",
    "cn_cdd_004",
    "cn_atm_cap_005",
    "cn_wallet_foreign_006",
    "cn_wise_in_007",
    "cn_wise_out_008",
    "cn_boc_anxin_009",
]
AUDIT_DAY = date(2026, 10, 9)
README = Path(__file__).resolve().parent.parent / "rails" / "knowledge" / "README.md"


@pytest.mark.parametrize("entry_id", REWRITTEN)
def test_every_entry_the_pass_touched_is_checked_by_cc_on_the_audit_day_and_awaits_a_second_check(entry_id):
    entry = load_knowledge()[entry_id]

    assert entry["checked_by"] == "CC"
    assert entry["second_check_by"] == ""
    assert date.fromisoformat(str(entry["date_checked"])) >= AUDIT_DAY


def test_no_entry_keeps_the_placeholder_s():
    assert all(entry["checked_by"] != "S" for entry in load_knowledge().values())


def test_the_pix_participants_are_the_ones_the_resolution_admits():
    statement = load_knowledge()["br_pix_instant_001"]["statement"]

    assert "Its participants are institutions authorized" not in statement
    for words in ("financial institutions, payment institutions and government entities", "half a million"):
        assert words in statement


def test_the_quota_entry_drops_the_january_and_study_abroad_sentences():
    statement = load_knowledge()["cn_fx_quota_001"]["statement"]

    assert "January 2026" not in statement and "Study abroad" not in statement
    assert "Individuals in China have an annual facilitation quota of 50,000 US dollars" in statement
    assert "5 December 2025" in statement


def test_the_hsbc_entries_state_their_scope_and_the_upload_rule():
    entries = load_knowledge()
    remit, docs = entries["cn_edu_remit_002"]["statement"], entries["cn_edu_docs_003"]["statement"]

    assert "the US, UK, Canada, Australia and Hong Kong SAR" in remit and "HSBC" in remit
    assert "Originals or scans of originals are accepted" not in docs
    assert "photos or scans of the original documents" in docs and "copies" in docs and "mobile banking" in docs


def test_the_due_diligence_entry_cites_the_peoples_bank_order_and_says_nothing_of_splitting():
    entry = load_knowledge()["cn_cdd_004"]

    assert entry["source_url"] == "https://www.pbc.gov.cn/tiaofasi/144941/144957/5916164/index.html"
    assert entry["source_type"] == "regulator"
    assert "structuring" not in entry["statement"] and "Splitting" not in entry["statement"]
    for words in ("1 January 2026", "5,000 yuan", "1,000 US dollars", "accuracy of the remitter's information"):
        assert words in entry["statement"]


def test_the_wallet_entry_says_the_central_bank_will_instruct_platforms_for_overseas_travellers():
    entry = load_knowledge()["cn_wallet_foreign_006"]

    assert "WeChat Pay" not in entry["statement"] and "Foreign bank cards" not in entry["statement"]
    for words in ("will instruct", "Alipay and Tenpay", "overseas travellers"):
        assert words in entry["statement"]
    assert (entry["values"]["single_transaction_limit"], entry["values"]["annual_limit"]) == (5000, 50000)


def test_the_wise_inbound_entry_says_who_unionpay_serves_and_what_the_id_decides():
    entry = load_knowledge()["cn_wise_in_007"]

    assert "recipient_condition" not in entry["values"]
    assert "for recipients with a Chinese national ID" not in entry["statement"]
    assert "both mainland and non mainland recipients" in entry["statement"]
    assert "Mainland Chinese National ID" in entry["statement"]


def test_the_wise_outbound_entry_moves_to_the_help_article_and_its_figures():
    entry = load_knowledge()["cn_wise_out_008"]

    assert entry["source_url"] == "https://wise.com/help/articles/2955298/guide-to-cny-transfers"
    assert "100,000" not in entry["statement"]
    assert "300,000 yuan" in entry["statement"] and "50,000 yuan" in entry["statement"]


def test_the_bank_of_china_entry_states_its_age_and_branches():
    statement = load_knowledge()["cn_boc_anxin_009"]["statement"]

    assert "2010" in statement and "Beijing" in statement and "Tianjin" in statement
    assert "in the student's own name" not in statement


def test_the_china_precheck_carries_the_bank_of_china_caveat():
    result = FakeRouter().precheck("remit_from_china", "cn_bank_remit_sim", {})

    assert rules.ANXIN_CAVEAT in result.review_triggers
    assert "2010" in rules.ANXIN_CAVEAT and rules.CN_FUNDING_ENTRY in rules.ANXIN_CAVEAT


def test_the_structuring_refusal_is_named_as_lifelines_own_policy():
    result = FakeRouter().precheck("remit_from_china", "cn_bank_remit_sim", {"senders": ["parent", "aunt_or_uncle"]})

    assert rules.STRUCTURING_POLICY in result.review_triggers
    assert "Lifeline's own policy" in rules.STRUCTURING_POLICY
    assert rules.NO_SINGAPORE_PAGE in result.review_triggers


def test_the_arrival_facts_quote_the_wise_entry_and_give_no_verdict_on_the_route():
    facts, ids = rules.arrival_facts()

    assert ids == [rules.WALLET_FOREIGN_ENTRY, rules.WISE_INBOUND_ENTRY]
    assert facts[2:] == [rules.NO_FOREIGN_CARD_CASH]
    assert not any("not this student's route" in fact for fact in facts)


def test_the_nus_entry_keeps_sps_check_and_says_a_person_must_open_it_in_a_browser():
    entry = load_knowledge()["sg_nus_fee_payment_003"]

    assert entry["checked_by"] == "SP"
    assert str(entry["date_checked"]) == "2026-10-08"
    assert "bot challenge" in entry["note"] and "browser" in entry["note"]


def test_the_readme_sets_the_rule_for_pages_tools_cannot_open_and_records_s_as_a_placeholder():
    text = README.read_text(encoding="utf-8")

    assert "a page that tools cannot open" in text
    assert "`S` in `checked_by` was a placeholder" in text
