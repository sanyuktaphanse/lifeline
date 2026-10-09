"""The rules the simulated rails and the router share, each read from a knowledge entry by its id.

No sourced figure is written here: every limit, purpose, and document list comes from `values` in the entry,
and every refusal names the entry it rests on. Source: docs/decisions.md, 8 October 2026. The one product
constant, the cash cap's warning lines, is named as Lifeline's own choice where it is defined.
"""

import re
import unicodedata
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.schemas import INSTRUMENT_ID, NonNegativeAmount
from core.format import format_amount
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
ATM_CAP_ENTRY = "cn_atm_cap_005"
WALLET_FOREIGN_ENTRY = "cn_wallet_foreign_006"
WISE_INBOUND_ENTRY = "cn_wise_in_007"
# Source: docs/decisions.md, 8 October 2026. No entry on file covers cash on a foreign card in China;
# cn_atm_cap_005 covers Chinese cards used abroad, not this.
NO_FOREIGN_CARD_CASH = "Lifeline has no sourced entry for cash withdrawals on a foreign card in China."
# Source: cn_edu_remit_002, whose page names the US, UK, Canada, Australia and Hong Kong SAR, and the audit of
# 9 October 2026 in docs/knowledge_audit.md.
NO_SINGAPORE_PAGE = (
    "The route above the quota rests on HSBC's education payment page, which lists institutions in the US, "
    "UK, Canada, Australia and Hong Kong, not Singapore, and Lifeline has no sourced Singapore page on file "
    f"for it. Source: {CN_INSTITUTION_ENTRY}."
)
# Source: docs/decisions.md, 9 October 2026, the knowledge corrections. cn_cdd_004's order gives a verification
# threshold and says nothing about splitting across people, so the refusal is Lifeline's own policy.
STRUCTURING_POLICY = (
    "Refusing to use several people's quotas for one student's costs is Lifeline's own policy, not a quoted "
    "rule: no source on file says that splitting a transfer across people is structuring."
)
# Source: cn_boc_anxin_009, whose page dates from 2010 and names eleven branches, and docs/decisions.md,
# 9 October 2026.
ANXIN_CAVEAT = (
    "The Bank of China page on file for the An Xin account is from 2010 and names only certain branches, so "
    "whether the account is still offered, and at which branch, must be confirmed with Bank of China. "
    f"Source: {CN_FUNDING_ENTRY}."
)
# Source: docs/decisions.md, Stage 9 of 8 October 2026. Lifeline's own choice, not a sourced figure: the
# percentages of the annual cap across all cards, and of each card's daily cap, at which the cash cap warns.
# cn_atm_cap_005 gives the caps; nothing on file gives a line to warn at. At 90 the warning carries the
# entry's consequence sentence.
CASH_CAP_WARNING_PERCENTS = (70, 90)
WISE_DOCS_ENTRY = "wise_docs_channel_001"
WISE_SCAM_ENTRY = "wise_docs_impersonation_002"
# The kinds of channel a provider's request for documents can name, never the address itself.
# Source: docs/decisions.md, 8 October 2026. Only the first two are inside the provider's own app or website.
UPLOAD_CHANNELS = ("provider_app_upload", "provider_website_upload")
DOCUMENT_CHANNELS = (*UPLOAD_CHANNELS, "email", "chat", "link", "phone", "post", "other")
# The names Wise goes by, as whole words. Source: the provider value of wise_docs_channel_001 and its old name.
WISE_NAMES = frozenset({"wise", "transferwise"})
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
                f"{format_amount(amount, currency, 'en')} would take the day's UPI to PayNow total to "
                f"{format_amount(earlier_today + amount, currency, 'en')}, above the daily cap of "
                f"{format_amount(cap['daily_cap'], cap['currency'], 'en')}. Source: {UPI_CAP_ENTRY}.",
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


# Letters from other scripts that look like Latin ones, as scam messages use them, such as a Cyrillic i in
# Wise. A short list for the letters of the provider names on file, not the whole Unicode table.
# Source: the attacker brief of 8 October.
LOOKALIKES = str.maketrans(
    {
        "\u0430": "a", "\u0435": "e", "\u0456": "i", "\u0131": "i", "\u03b9": "i", "\u043e": "o",
        "\u03bf": "o", "\u0440": "p", "\u0441": "c", "\u0455": "s", "\u0443": "y", "\u0445": "x",
        "\u051d": "w", "\u0461": "w", "\u03c9": "w", "\u0457": "i", "\u0410": "a", "\u0415": "e",
        "\u0406": "i", "\u041e": "o", "\u0420": "p", "\u0421": "c", "\u0405": "s", "\u051c": "w",
    }
)


def is_wise(provider: str) -> bool:
    """Whether a provider name is Wise, however it is written: any case, fullwidth, with accents, with
    lookalike letters from another script, with invisible characters, or inside a domain."""
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", provider).translate(LOOKALIKES))
    plain = "".join(char for char in folded if unicodedata.category(char) not in ("Mn", "Cf"))
    words = re.findall(r"[a-z]+", plain.casefold().translate(LOOKALIKES))
    return any(word in WISE_NAMES for word in words)


def document_request(provider: str, channel: str | None) -> tuple[bool | None, list[str], list[str]]:
    """Whether a request for documents arrives the way the provider collects them, by its entries.

    Returns ready, the review triggers and the entry ids. A channel that is not an upload inside the
    provider's own app or website is not ready. A provider with no entry gets no verdict.
    """
    if not is_wise(provider):
        return None, ["Lifeline has no sourced entry on how this provider collects documents."], []
    if channel in UPLOAD_CHANNELS:
        return True, [entry(WISE_DOCS_ENTRY)["statement"]], [WISE_DOCS_ENTRY]
    ids = [WISE_DOCS_ENTRY, WISE_SCAM_ENTRY]
    return False, [entry(entry_id)["statement"] for entry_id in ids], ids


def several_quotas(user_context: dict[str, Any]) -> bool:
    """Whether a plan uses more than one person's quota for one student: said so, or more than one sender."""
    return user_context.get("multiple_people_quota") is True or len(user_context.get("senders") or []) > 1


def structuring_refusal() -> tuple[list[str], list[str]]:
    """Why splitting across people is refused, as Lifeline's own policy, beside the verification rule and the
    documented route above the quota, by their entries."""
    ids = [CN_CDD_ENTRY, CN_QUOTA_ENTRY, CN_INSTITUTION_ENTRY]
    return [STRUCTURING_POLICY, *(entry(entry_id)["statement"] for entry_id in ids), NO_SINGAPORE_PAGE], ids


class ChineseCard(BaseModel):
    """One Chinese bank card from a fixture, with the yuan withdrawn overseas on it so far."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: str = Field(pattern=f"^{INSTRUMENT_ID}$")
    withdrawn_this_year: NonNegativeAmount
    withdrawn_today: NonNegativeAmount


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def with_withdrawals(
    cards: list[dict[str, Any]], withdrawals: Iterable[dict[str, Any]], today: date
) -> list[dict[str, Any]]:
    """Each card's starting position from the fixture plus the withdrawals recorded on it.

    A withdrawal counts toward the year when it was made in today's calendar year, and toward the day when it
    was made today. A withdrawal on a card the fixture does not hold, or with no readable day, is not counted.
    """
    added_year: dict[str, Decimal] = {}
    added_today: dict[str, Decimal] = {}
    for withdrawal in withdrawals:
        made = _day(withdrawal.get("date"))
        if made is None or made.year != today.year:
            continue
        card = str(withdrawal.get("instrument_id"))
        amount = Decimal(str(withdrawal.get("amount")))
        added_year[card] = added_year.get(card, Decimal(0)) + amount
        if made == today:
            added_today[card] = added_today.get(card, Decimal(0)) + amount
    return [
        {
            **card,
            "withdrawn_this_year": Decimal(str(card.get("withdrawn_this_year")))
            + added_year.get(str(card.get("instrument_id")), Decimal(0)),
            "withdrawn_today": Decimal(str(card.get("withdrawn_today")))
            + added_today.get(str(card.get("instrument_id")), Decimal(0)),
        }
        for card in cards
    ]


def _line_reached(used: Decimal, cap: Decimal) -> int | None:
    """The highest of Lifeline's warning lines the amount has reached, compared exactly, or None."""
    return max((level for level in CASH_CAP_WARNING_PERCENTS if used * 100 >= cap * level), default=None)


def cash_cap_status(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """What is left of the overseas cash cap, by cn_atm_cap_005, for the cards a fixture holds.

    The annual cap counts every card of the individual together, so the year's remainder is shared by
    every card; a card's remainder today is the smaller of its own daily remainder and that. It warns
    when the year's remainder is at or below one card's daily cap or what all the cards together may
    still take today. A fixture that cannot be true is refused. No figure is written here.
    """
    try:
        held = [ChineseCard.model_validate(card) for card in cards]
    except ValidationError as error:
        raise ValueError(f"A Chinese card in the fixture is malformed: {error}") from error
    values = entry(ATM_CAP_ENTRY)["values"]
    annual, daily = Decimal(str(values["annual_cap"])), Decimal(str(values["per_card_daily_cap"]))
    ids = [card.instrument_id for card in held]
    if len(set(ids)) != len(ids):
        raise ValueError("A Chinese card appears twice in the fixture.")
    for card in held:
        # Today's withdrawals are part of the year's and within the daily cap, or the fixture cannot be true.
        if card.withdrawn_today > card.withdrawn_this_year or card.withdrawn_today > daily:
            raise ValueError(f"Card {card.instrument_id} in the fixture has withdrawals today that cannot be true.")
    used_year = sum((card.withdrawn_this_year for card in held), Decimal(0))
    remaining_year = max(annual - used_year, Decimal(0))
    # The lines are read across all cards for the year, so splitting across cards or days cannot hide one,
    # and per card for the day, as the entry caps each card per day.
    thresholds: list[dict[str, Any]] = []
    year_level = _line_reached(used_year, annual)
    if year_level is not None:
        thresholds.append({"scope": "year", "level": year_level, "used": used_year, "cap": annual})
    for card in held:
        day_level = _line_reached(card.withdrawn_today, daily)
        if day_level is not None:
            thresholds.append(
                {"scope": "card_day", "instrument_id": card.instrument_id, "level": day_level,
                 "used": card.withdrawn_today, "cap": daily}
            )
    # What all the cards together may still take today, each within its own daily cap. Source: the
    # attacker brief of 8 October: two cards can reach the cap in one day while each is under it.
    cards_today_total = sum((daily - card.withdrawn_today for card in held), Decimal(0))
    return {
        "used_year": used_year,
        "annual_cap": annual,
        "thresholds": thresholds,
        "remaining_year": remaining_year,
        "per_card_daily_cap": daily,
        "cards_today_total": cards_today_total,
        "currency": values["currency"],
        "warn": bool(held) and remaining_year <= max(daily, cards_today_total),
        "cards": [
            {
                "instrument_id": card.instrument_id,
                "remaining_year": remaining_year,
                "remaining_today": min(max(daily - card.withdrawn_today, Decimal(0)), remaining_year),
            }
            for card in held
        ],
    }


def cash_cap_sentences(cards: list[dict[str, Any]]) -> tuple[bool | None, list[str], list[str]]:
    """The overseas cash precheck: ready, one sentence per card and the consequence, and the entry id."""
    if not cards:
        return None, ["Lifeline has no record of overseas cash withdrawals on your Chinese bank cards."], []
    status = cash_cap_status(cards)
    currency = status["currency"]
    sentences = [
        f"Card {card['instrument_id']}: {format_amount(card['remaining_year'], currency, 'en', grouped=True)} left this "
        f"calendar year across all Chinese cards, and {format_amount(card['remaining_today'], currency, 'en', grouped=True)} "
        f"left today. Source: {ATM_CAP_ENTRY}."
        for card in status["cards"]
    ]
    sentences.append(entry(ATM_CAP_ENTRY)["values"]["consequence"])
    return not status["warn"], sentences, [ATM_CAP_ENTRY]


def arrival_facts() -> tuple[list[str], list[str]]:
    """What a foreign student arriving in China is told, from cn_wallet_foreign_006 and cn_wise_in_007 only.

    Both entries are quoted whole. Lifeline gives no verdict on whether the Wise route fits the student,
    because its page says UnionPay serves recipients with or without a mainland ID and the ID decides only
    the banks. Cash on a foreign card has no entry.
    """
    ids = [WALLET_FOREIGN_ENTRY, WISE_INBOUND_ENTRY]
    return [*(entry(entry_id)["statement"] for entry_id in ids), NO_FOREIGN_CARD_CASH], ids
