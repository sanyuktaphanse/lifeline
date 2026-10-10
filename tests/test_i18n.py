"""Stage 13, the multilingual review: every key in every language, one formatter for amounts and dates,
the wrapper for English text inside a reply in another language, the direction flags for the app, and the
reply to a language Lifeline cannot write in. Source: docs/decisions.md and docs/i18n_review.md."""

import ast
import inspect
import re
import string
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from contracts.schemas import LANGUAGE_META, LANGUAGES
from core import agent, mandate, monthly
from core.agent import HAND_TRANSLATED, INJECTION_WHAT, PENDING, QUOTED, REDACTION_MARKER, SUMMARY_WHAT, TEXTS, _text
from core.format import fill, format_amount, format_date
from rails.knowledge.loader import load_knowledge
from rails.sim import rules
from rails.sim.rules import ATM_CAP_ENTRY, CN_CDD_ENTRY, WISE_DOCS_ENTRY, WISE_INBOUND_ENTRY
from tests.test_agent import RENT, USER, _call, _say, _setup, _user

ROOT = Path(__file__).resolve().parent.parent
# Every table a student can read a sentence from, by the name the review file uses for it.
TABLES = {
    "core.agent.TEXTS": TEXTS,
    "core.agent.INJECTION_WHAT": INJECTION_WHAT,
    "core.agent.SUMMARY_WHAT": SUMMARY_WHAT,
    "core.monthly.TEXTS": monthly.TEXTS,
}
# The modules that turn an amount or a date into text for a student. The engine's reasons reach the student
# inside every refusal, and the rail rules' sentences inside a refusal or a precheck.
STUDENT_TEXT_MODULES = (agent, monthly, rules, mandate)
# The names an f-string sentence in the engine or the rail rules may hold an amount or a date under.
AMOUNT_LIKE = re.compile(r"amount|cap\b|cap\[|earlier|remaining|used|total|limit|tolerance")
DATE_LIKE = re.compile(r"requested_at|valid_from|valid_until|allowed_from|withdrawal_date|_utc_date")


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _lead(lang: str, key: str = QUOTED) -> str:
    """A wrapper's own sentence in a language, without the text it wraps. QUOTED wraps sourced text, PENDING
    wraps Lifeline's own English sentences."""
    return TEXTS[lang][key].replace("{text}", "")


# One. The inventory.


@pytest.mark.parametrize("table_name", TABLES)
def test_every_table_has_exactly_the_languages_lifeline_replies_in(table_name):
    assert set(TABLES[table_name]) == set(LANGUAGES)


@pytest.mark.parametrize("table_name", TABLES)
def test_every_key_is_present_in_every_language(table_name):
    table = TABLES[table_name]
    keys = set().union(*(table[lang] for lang in LANGUAGES))
    missing = {lang: sorted(keys - set(table[lang])) for lang in LANGUAGES if keys - set(table[lang])}
    assert missing == {}


@pytest.mark.parametrize("table_name", TABLES)
def test_every_key_has_the_same_placeholders_in_every_language(table_name):
    table = TABLES[table_name]
    # Only the named, documented exceptions may drop a placeholder, and only outside English.
    exceptions = HAND_TRANSLATED if table is TEXTS else {}
    differ = {}
    for key, english in table["en"].items():
        for lang in LANGUAGES:
            expected = _fields(english) - (exceptions.get(key, frozenset()) if lang != "en" else frozenset())
            if _fields(table[lang][key]) != expected:
                differ[(key, lang)] = sorted(_fields(table[lang][key]) ^ expected)
    assert differ == {}


def test_the_hand_translated_exceptions_name_real_english_placeholders_and_nothing_else():
    assert HAND_TRANSLATED == {
        "cash_cap_warning": frozenset({"consequence"}),
        "cash_cap_year_consequence": frozenset({"consequence"}),
    }
    for key, names in HAND_TRANSLATED.items():
        assert names <= _fields(TEXTS["en"][key])
        for lang in LANGUAGES:
            if lang != "en":
                assert not names & _fields(TEXTS[lang][key])


def test_the_hand_translation_of_the_consequence_says_what_the_entry_says():
    consequence = load_knowledge()[ATM_CAP_ENTRY]["values"]["consequence"]
    assert consequence == "Exceeding the annual cap bars overseas withdrawals for the rest of that year and the following year."
    for key in HAND_TRANSLATED:
        assert "Ultrapassar o limite anual bloqueia saques no exterior pelo resto daquele ano e durante o ano seguinte." in TEXTS["pt"][key]
        assert "超过年度额度后，当年余下时间和下一年都不能在境外取现。" in TEXTS["zh"][key]


# The wrapper for English inside a reply in another language.


@pytest.mark.parametrize("key", [QUOTED, PENDING])
def test_each_wrapper_is_a_no_op_in_english_and_one_sentence_before_the_text_elsewhere(key):
    assert TEXTS["en"][key] == "{text}"
    for lang in LANGUAGES:
        assert _fields(TEXTS[lang][key]) == {"text"}
        assert TEXTS[lang][key].endswith("{text}")
    for lang in ("pt", "zh"):
        assert _lead(lang, key).strip()


def test_the_two_wrappers_say_different_things_in_every_other_language():
    for lang in ("pt", "zh"):
        assert _lead(lang, QUOTED) != _lead(lang, PENDING)


def test_the_wrappers_add_nothing_to_empty_text_or_to_english():
    for wrap in (agent._quoted, agent._pending):
        assert wrap("pt", "") == ""
        assert wrap("en", "Source: x.") == "Source: x."


def test_only_a_knowledge_entrys_statement_is_wrapped_as_sourced_and_never_as_pending():
    tree = ast.parse(inspect.getsource(agent))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("_quoted", "_pending")]
    sourced = [ast.unparse(call.args[1]) for call in calls if call.func.id == "_quoted"]
    pending = [ast.unparse(call.args[1]) for call in calls if call.func.id == "_pending"]
    assert sourced and pending
    assert [arg for arg in sourced if "statement" not in arg and arg != "rule"] == []
    assert [arg for arg in pending if "statement" in arg] == []


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_a_refusal_in_another_language_carries_its_reasons_in_english_behind_the_wrapper(lang):
    s = _setup([_call("propose_transfer", {**RENT, "payee_id": "stranger_99"})])

    reply = s.loop.handle(USER, _user("pague", lang=lang))

    assert not reply.decision.allowed
    reasons = " ".join(reply.decision.reasons)
    assert reasons
    assert f"{_lead(lang, PENDING)}{reasons}" in reply.text
    assert _lead(lang, QUOTED) not in reply.text


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_the_credentials_refusal_carries_its_reasons_behind_the_wrapper(lang):
    s = _setup([_call("export_credentials", {})])

    reply = s.loop.handle(USER, _user("card number", lang=lang))

    assert f"{_lead(lang, PENDING)}{' '.join(reply.decision.reasons)}" in reply.text


def test_an_english_refusal_is_unchanged_by_the_wrapper():
    s = _setup([_call("propose_transfer", {**RENT, "payee_id": "stranger_99"})])

    reply = s.loop.handle(USER, _user("pay", lang="en"))

    rules_text = ", ".join(reply.decision.rule_ids)
    summary = f"This turn: a transfer of 1200 SGD to stranger_99: refused under {rules_text}."
    assert reply.text == f"I cannot do that. Rules: {rules_text}. {' '.join(reply.decision.reasons)} {summary}"


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_the_arrival_facts_are_quoted_in_english_behind_the_wrapper(lang):
    s = _setup([_call("precheck", {"action_kind": "arrive_in_china", "provider": "alipay"}), _say("")])

    reply = s.loop.handle(USER, _user("chegando", lang=lang))

    assert f"{_lead(lang)}{load_knowledge()['cn_wallet_foreign_006']['statement']}" in reply.text
    assert f"{_lead(lang, PENDING)}{rules.NO_FOREIGN_CARD_CASH}" in reply.text
    assert "not this student's route" not in reply.text
    assert WISE_INBOUND_ENTRY in reply.text


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_the_structuring_refusal_quotes_its_entries_behind_the_wrapper(lang):
    call = _call("precheck", {"action_kind": "remit_from_china", "provider": "cn_bank_remit_sim", "senders": ["parent", "aunt_or_uncle"]})
    s = _setup([call, _say("")])

    reply = s.loop.handle(USER, _user("enviar", lang=lang))

    statement = load_knowledge()[CN_CDD_ENTRY]["statement"]
    assert f"{_lead(lang)}{statement}" in reply.text
    assert reply.text.count(_lead(lang)) == 2
    assert f"{_lead(lang, PENDING)}{rules.STRUCTURING_POLICY}" in reply.text
    assert f"{_lead(lang, PENDING)}{rules.NO_SINGAPORE_PAGE}" in reply.text


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_the_document_request_flag_quotes_its_entries_behind_the_wrapper(lang):
    call = _call("precheck", {"action_kind": "document_request", "provider": "wise", "channel": "email"})
    s = _setup([call, _say("")])

    reply = s.loop.handle(USER, _user("documentos", lang=lang))

    assert f"{_lead(lang)}{load_knowledge()[WISE_DOCS_ENTRY]['statement']}" in reply.text


@pytest.mark.parametrize("lang", ["pt", "zh"])
def test_a_rescue_quotes_its_cash_options_and_card_estimate_behind_the_wrapper(lang):
    from tests.test_rescue import CASH_ID, ESTIMATE_ID, NO_BACKUP, _confirm, _setup as _rescue_setup, _to_freeze

    rescue = _rescue_setup(NO_BACKUP)
    done = _confirm(rescue, _to_freeze(rescue, lang), lang=lang)

    entries = load_knowledge()
    assert f"{_lead(lang)}{entries[CASH_ID]['statement']}" in done.text
    assert f"{_lead(lang)}{entries[ESTIMATE_ID]['statement']}" in done.text


# The English only sentences, kept this stage and pinned, so none can change without this test and
# docs/i18n_review.md changing with it.


def test_the_english_only_sentences_outside_any_table_are_pinned():
    assert REDACTION_MARKER == "[redacted]"
    assert rules.NO_FOREIGN_CARD_CASH == "Lifeline has no sourced entry for cash withdrawals on a foreign card in China."
    assert rules.NO_SINGAPORE_PAGE == (
        "The route above the quota rests on HSBC's education payment page, which lists institutions in the US, "
        "UK, Canada, Australia and Hong Kong, not Singapore, and Lifeline has no sourced Singapore page on file "
        "for it. Source: cn_edu_remit_002."
    )
    assert rules.no_duration("cn_boc_anxin_009") == "Lifeline has no sourced duration on file for this transfer. Source: cn_boc_anxin_009."
    assert rules.upi_refusals(Decimal("70000"), "INR", "gift", Decimal("0")) == [
        (
            "in_upi_paynow_cap_002",
            "70000 INR would take the day's UPI to PayNow total to 70000 INR, above the daily cap of 60000 INR. "
            "Source: in_upi_paynow_cap_002.",
        )
    ]
    assert rules.upi_refusals(Decimal("600"), "SGD", "gift", Decimal("0")) == [
        ("in_upi_paynow_cap_002", "Lifeline has no sourced UPI to PayNow limit in SGD. Source: in_upi_paynow_cap_002.")
    ]
    assert rules.pix_refusals("maria", frozenset()) == [
        (
            "br_pix_keys_002",
            "Pix reaches a payee only through a Pix key, and no Pix key is on file for 'maria'. Source: br_pix_keys_002.",
        )
    ]
    assert rules.cn_purpose_refusals("gift") == [
        (
            "cn_boc_anxin_009",
            "Lifeline has no sourced rule on file for 'gift' from China to Singapore. Sources: cn_boc_anxin_009, sg_nus_fee_payment_003.",
        )
    ]
    assert rules.document_request("otherbank", "email") == (None, ["Lifeline has no sourced entry on how this provider collects documents."], [])
    assert rules.cash_cap_sentences([]) == (None, ["Lifeline has no record of overseas cash withdrawals on your Chinese bank cards."], [])
    card = {"instrument_id": "icbc:card_03", "withdrawn_this_year": "95000", "withdrawn_today": "1000"}
    assert rules.cash_cap_sentences([card])[1][0] == (
        "Card icbc:card_03: 5,000 CNY left this calendar year across all Chinese cards, and 5,000 CNY left today. "
        "Source: cn_atm_cap_005."
    )
    assert rules.arrival_facts()[0][2] == rules.NO_FOREIGN_CARD_CASH
    assert rules.STRUCTURING_POLICY == (
        "Refusing to use several people's quotas for one student's costs is Lifeline's own policy, not a quoted "
        "rule: no source on file says that splitting a transfer across people is structuring."
    )
    assert rules.ANXIN_CAVEAT == (
        "The Bank of China page on file for the An Xin account is from 2010 and names only certain branches, so "
        "whether the account is still offered, and at which branch, must be confirmed with Bank of China. "
        "Source: cn_boc_anxin_009."
    )


# Three. Amounts and dates.


@pytest.mark.parametrize("lang", LANGUAGES)
def test_an_amount_is_written_as_the_templates_wrote_it_in_every_language(lang):
    assert format_amount(Decimal("1200"), "SGD", lang) == "1200 SGD"
    assert format_amount(Decimal("1200.50"), "SGD", lang) == "1200.50 SGD"
    assert format_amount(Decimal("0.00"), "SGD", lang) == "0.00 SGD"
    assert format_amount("1400", "BRL", lang) == "1400 BRL"
    assert format_amount(60000, "INR", lang) == "60000 INR"
    assert format_amount(Decimal("5"), None, lang) == "5"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_a_grouped_amount_is_written_with_a_comma_every_three_digits_as_the_cash_cap_wrote_it(lang):
    for value in (Decimal("100000"), Decimal("5000"), Decimal("950"), Decimal("12345.67")):
        assert format_amount(value, "CNY", lang, grouped=True) == f"{value:,} CNY"
    assert format_amount(Decimal("30000"), None, lang, grouped=True) == "30,000"


def test_an_amount_with_an_exponent_is_written_out_in_full():
    assert format_amount(Decimal("1.4E+3"), "SGD", "en") == "1400 SGD"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_a_date_and_a_moment_are_written_as_the_templates_wrote_them(lang):
    assert format_date(date(2026, 10, 12), lang) == "2026-10-12"
    moment = datetime(2026, 10, 12, 9, 30, 15, 123456, tzinfo=timezone.utc)
    assert format_date(moment, lang) == moment.isoformat(timespec="seconds") == "2026-10-12T09:30:15+00:00"


@pytest.mark.parametrize("value", [Decimal("1200"), 1200.0, date(2026, 10, 12), datetime(2026, 10, 12, tzinfo=timezone.utc)])
def test_no_student_sentence_takes_a_decimal_a_float_or_a_date_unformatted(value):
    with pytest.raises(TypeError):
        _text("en", "notice_sent", amount=value, payee="landlord_sp")
    with pytest.raises(TypeError):
        fill(monthly.TEXTS["en"]["reminder_due"], due=value)


def test_no_template_names_a_currency_apart_from_its_amount():
    for table_name, table in TABLES.items():
        for lang in LANGUAGES:
            for key, template in table[lang].items():
                assert "currency" not in _fields(template), (table_name, lang, key)


@pytest.mark.parametrize("module", STUDENT_TEXT_MODULES, ids=lambda module: module.__name__)
def test_no_student_facing_module_formats_a_number_with_its_own_format_spec(module):
    tree = ast.parse(inspect.getsource(module))
    specs = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None
        # A month number padded to two digits, as in 2026-09, is the month's id and no amount or date.
        and ast.unparse(node.format_spec) != "f'02d'"
    ]
    assert specs == []


@pytest.mark.parametrize("module", (rules, mandate), ids=lambda module: module.__name__)
def test_every_amount_and_date_an_english_sentence_holds_goes_through_the_formatter(module):
    tree = ast.parse(inspect.getsource(module))
    loose = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FormattedValue):
            continue
        written = ast.unparse(node.value)
        called = getattr(node.value.func, "id", "") if isinstance(node.value, ast.Call) else ""
        if AMOUNT_LIKE.search(written) and called not in ("format_amount", "format_date"):
            loose.append(written)
        elif DATE_LIKE.search(written) and called != "format_date":
            loose.append(written)
    assert loose == []


def test_the_formatter_says_locale_display_is_the_apps_job():
    source = (ROOT / "core" / "format.py").read_text(encoding="utf-8")
    assert "the app's job" in source
    assert "docs/decisions.md" in source


# Four. Direction flags for the app.


def test_language_meta_names_every_language_and_nothing_else():
    assert tuple(LANGUAGE_META) == LANGUAGES


def test_every_language_today_is_written_left_to_right_and_named_in_its_own_script():
    assert {code: meta["direction"] for code, meta in LANGUAGE_META.items()} == {"en": "ltr", "pt": "ltr", "zh": "ltr"}
    assert {code: meta["name"] for code, meta in LANGUAGE_META.items()} == {"en": "English", "pt": "Português", "zh": "中文"}


def test_health_serves_the_language_meta_so_the_app_never_hardcodes_it():
    from tests.test_api import _client

    response = _client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "languages": LANGUAGE_META}


# Five. A language Lifeline cannot write in.

HINDI = "मेरे कार्ड का नंबर क्या है?"
SPANISH = "¿Cuál es el número de mi tarjeta?"


@pytest.mark.parametrize("text", [HINDI, SPANISH])
def test_a_turn_in_a_language_lifeline_cannot_detect_is_answered_in_english_with_the_code_en(text):
    s = _setup([_call("export_credentials", {})])

    reply = s.loop.handle(USER, _user(text))

    assert agent.detect_lang(text) == "en"
    assert reply.lang == "en"
    assert reply.text.startswith("Lifeline never shows card numbers")


def test_a_spanish_turn_with_a_word_portuguese_shares_is_detected_as_portuguese():
    # Pinned as it is: saldo and favor are Portuguese words on the list and Spanish words too. Open item in
    # docs/i18n_review.md.
    assert agent.detect_lang("¿Cuál es mi saldo, por favor?") == "pt"


@pytest.mark.parametrize("code", ["hi", "es"])
def test_an_explicit_code_lifeline_cannot_write_in_is_echoed_back_with_english_text(code):
    s = _setup([_call("export_credentials", {})])

    reply = s.loop.handle(USER, _user(HINDI if code == "hi" else SPANISH, lang=code))

    assert reply.lang == code
    assert reply.text.startswith("Lifeline never shows card numbers")


@pytest.mark.parametrize("code", ["hi", "es"])
def test_an_explicit_code_lifeline_cannot_write_in_is_refused_over_http(code):
    from tests.test_api import _client

    response = _client().post("/chat", json={"user_id": USER, "text": HINDI, "lang": code})

    assert response.status_code == 422
