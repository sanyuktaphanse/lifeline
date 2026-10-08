from decimal import Decimal

import pytest

from rails.knowledge.loader import load_knowledge

# Source: the entries themselves. Each id is one a simulated rail or the router reads.
RAIL_ENTRIES = {
    "in_upi_paynow_purpose_001": "https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=3415",
    "in_upi_paynow_cap_002": "https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=3415",
    "br_pix_instant_001": "https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf",
    "br_pix_keys_002": "https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf",
    "cn_boc_anxin_009": "https://www.boc.cn/en/pbservice/pb4/201005/t20100520_1323963.html",
    "sg_nus_fee_payment_003": "https://www.nus.edu.sg/finance/students/student-finance-matters/payments/other-payment-modes",
}


@pytest.mark.parametrize(("entry_id", "url"), RAIL_ENTRIES.items())
def test_every_entry_a_rail_reads_exists_with_its_source_and_awaits_a_second_check(entry_id, url):
    entry = load_knowledge()[entry_id]

    assert entry["source_url"] == url
    assert entry["second_check_by"] == ""
    assert entry["checked_by"] in {"CC", "SP"}


def test_the_nus_entry_says_sp_opened_it_because_the_tool_was_blocked():
    entry = load_knowledge()["sg_nus_fee_payment_003"]

    assert entry["checked_by"] == "SP"
    assert "SP" in entry["note"] and "blocked" in entry["note"]


def _values():
    for entry in load_knowledge().values():
        for name, value in (entry.get("values") or {}).items():
            yield entry, name, value


def test_every_number_in_values_is_written_in_its_statement():
    for entry, name, value in _values():
        if isinstance(value, (int, str)) and str(value).replace(".", "").isdigit():
            if name == "typical_duration_hours" and Decimal(str(value)) == 0:
                assert "real time" in entry["statement"], f"{entry['id']} gives no duration of zero in words"
                continue
            written = f"{Decimal(str(value)):,}"
            assert written in entry["statement"], f"{entry['id']} {name} {written} is not in its statement"


def test_the_upi_paynow_cap_is_the_rbi_figure_in_rupees():
    values = load_knowledge()["in_upi_paynow_cap_002"]["values"]

    assert (Decimal(str(values["daily_cap"])), values["currency"]) == (Decimal("60000"), "INR")


def test_the_upi_paynow_purposes_are_exactly_the_rbi_two():
    entry = load_knowledge()["in_upi_paynow_purpose_001"]

    assert entry["values"]["purposes"] == ["maintenance_of_relatives_abroad", "gift"]
    assert "Maintenance of Relatives Abroad" in entry["statement"] and "Gift" in entry["statement"]


def test_pix_settles_in_real_time_and_names_its_keys():
    entries = load_knowledge()

    assert "real time" in entries["br_pix_instant_001"]["statement"]
    assert entries["br_pix_instant_001"]["values"]["typical_duration_hours"] == 0
    for key in ("cell phone number", "e-mail", "CPF", "CNPJ", "random key"):
        assert key in entries["br_pix_keys_002"]["statement"]


def test_the_bank_of_china_checklist_is_the_pages_three_originals():
    entry = load_knowledge()["cn_boc_anxin_009"]

    assert entry["values"]["documents"] == ["passport", "ID card or Hukou book", "enrollment or admission letter"]
    for document in entry["values"]["documents"]:
        assert document in entry["statement"]
