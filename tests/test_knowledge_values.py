import re
from decimal import Decimal, InvalidOperation

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


def _numbers(value):
    """Every number inside a value, lists and mappings included, as plain decimal text."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float, Decimal)):
        return [format(Decimal(str(value)).normalize(), "f")]
    if isinstance(value, str):
        try:
            return [format(Decimal(value).normalize(), "f")]
        except InvalidOperation:
            return []
    if isinstance(value, dict):
        return [n for item in value.values() for n in _numbers(item)]
    if isinstance(value, list):
        return [n for item in value for n in _numbers(item)]
    return []


def unbacked_numbers(entry) -> list[str]:
    """The numbers in an entry's values that its statement does not write as whole numbers.

    A number counts as written when it appears with its thousands separators and not as part of a
    longer number, so 60 is not found inside 60,000. A duration of zero is written as real time.
    """
    statement = entry["statement"]
    missing = []
    for name, value in (entry.get("values") or {}).items():
        for number in _numbers(value):
            if name == "typical_duration_hours" and Decimal(number) == 0 and "real time" in statement:
                continue
            written = f"{Decimal(number):,}"
            if not re.search(rf"(?<![\d,.]){re.escape(written)}(?![\d]|[,.]\d)", statement):
                missing.append(number)
    return missing


def test_every_number_in_values_is_written_in_its_statement():
    for entry in load_knowledge().values():
        assert unbacked_numbers(entry) == [], f"{entry['id']} has numbers its statement does not write"


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


@pytest.mark.parametrize(
    ("values", "unbacked"),
    [
        ({"daily_cap": 70000.0}, ["70000"]),
        ({"daily_cap": 60}, ["60"]),
        ({"caps": [70000]}, ["70000"]),
        ({"nested": {"cap": 70000}}, ["70000"]),
        ({"daily_cap": 60000, "currency": "INR"}, []),
        ({"daily_cap": "60000"}, []),
        ({"daily_cap": 60000.0}, []),
    ],
)
def test_the_values_check_finds_every_number_its_statement_does_not_write(values, unbacked):
    entry = {"id": "xx_check_001", "statement": "A daily limit of 60,000 rupees.", "values": values}

    assert unbacked_numbers(entry) == unbacked


def test_every_entry_the_rail_rules_name_exists():
    import rails.sim.rules as rules

    named = {value for name, value in vars(rules).items() if name.endswith("_ENTRY")}

    assert named <= set(load_knowledge())
