"""The rules the simulated rails and the router share, each read from a knowledge entry by its id.

No figure is written here: every limit, purpose, and document list comes from `values` in the entry,
and every refusal names the entry it rests on. Source: docs/decisions.md, 8 October 2026.
"""

from decimal import Decimal
from fractions import Fraction
from typing import Any

from rails.knowledge.loader import load_knowledge

UPI_PURPOSE_ENTRY = "in_upi_paynow_purpose_001"
UPI_CAP_ENTRY = "in_upi_paynow_cap_002"
PIX_SCHEME_ENTRY = "br_pix_instant_001"
PIX_KEYS_ENTRY = "br_pix_keys_002"
CN_FUNDING_ENTRY = "cn_boc_anxin_009"
CN_INSTITUTION_ENTRY = "cn_edu_remit_002"
CN_QUOTA_ENTRY = "cn_fx_quota_001"
CN_CDD_ENTRY = "cn_cdd_004"
NUS_FEE_ENTRY = "sg_nus_fee_payment_003"
# The two purposes the China rail tells apart: paying the institution, and funding the student.
TUITION = "tuition"
LIVING_COSTS = "living_costs"

Refusal = tuple[str, str]


def entry(entry_id: str) -> dict[str, Any]:
    return load_knowledge()[entry_id]


def no_duration(entry_id: str) -> str:
    return f"Lifeline has no sourced duration on file for this transfer. Source: {entry_id}."


def upi_refusals(amount: Decimal, currency: str, purpose: str | None, earlier_today: Decimal) -> list[Refusal]:
    """Why UPI to PayNow cannot carry this, by the entries for its purposes and its daily cap."""
    refusals: list[Refusal] = []
    purposes = entry(UPI_PURPOSE_ENTRY)["values"]["purposes"]
    if purpose not in purposes:
        refusals.append(
            (
                UPI_PURPOSE_ENTRY,
                f"UPI to PayNow carries only person to person remittances for {' and '.join(purposes)}, "
                f"not {purpose!r}. Source: {UPI_PURPOSE_ENTRY}.",
            )
        )
    cap = entry(UPI_CAP_ENTRY)["values"]
    if currency != cap["currency"]:
        refusals.append(
            (UPI_CAP_ENTRY, f"Lifeline has no sourced UPI to PayNow limit in {currency}. Source: {UPI_CAP_ENTRY}.")
        )
    # Compared as exact fractions, so no decimal precision can round a sum back under the cap.
    elif Fraction(earlier_today) + Fraction(amount) > Fraction(str(cap["daily_cap"])):
        refusals.append(
            (
                UPI_CAP_ENTRY,
                f"{amount} {currency} would take the day's UPI to PayNow total to {earlier_today + amount} "
                f"{currency}, above the daily cap of {cap['daily_cap']} {cap['currency']}. Source: {UPI_CAP_ENTRY}.",
            )
        )
    return refusals


def pix_refusals(payee_id: str | None, pix_key_on_file: frozenset[str]) -> list[Refusal]:
    """Pix reaches a payee only through a Pix key, so a payee with no key on file cannot be paid."""
    if payee_id in pix_key_on_file:
        return []
    return [
        (
            PIX_KEYS_ENTRY,
            f"Pix reaches a payee only through a Pix key, and no Pix key is on file for {payee_id!r}. "
            f"Source: {PIX_KEYS_ENTRY}.",
        )
    ]


def cn_purpose_refusals(purpose: str | None) -> list[Refusal]:
    """What the entries allow from China to Singapore, by purpose: never paying the institution directly."""
    if purpose == TUITION:
        return [
            (
                NUS_FEE_ENTRY,
                "NUS asks for payment through Flywire or Convera, and Lifeline has no sourced rule on file for "
                f"a direct bank remittance to the institution. {entry(NUS_FEE_ENTRY)['statement']} "
                f"Sources: {NUS_FEE_ENTRY}, {CN_INSTITUTION_ENTRY}.",
            )
        ]
    if purpose == LIVING_COSTS:
        return []
    return [
        (
            CN_FUNDING_ENTRY,
            f"Lifeline has no sourced rule on file for {purpose!r} from China to Singapore. "
            f"Sources: {CN_FUNDING_ENTRY}, {NUS_FEE_ENTRY}.",
        )
    ]


def cn_documents() -> list[str]:
    return list(entry(CN_FUNDING_ENTRY)["values"]["documents"])
