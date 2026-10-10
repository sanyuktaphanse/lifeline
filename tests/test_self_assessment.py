"""The self assessment's numbers and citations, checked against their sources.

docs/self_assessment.md is a submission document. Its result sections carry numbers that come from the harness,
from pytest's collection, from the section Attacks attempted and held of the technical reference and from
docs/stranger_test.md, and every claim cites a test by file and function. These tests rebuild each number's
sentence from its source and fail when the document no longer says it, or when a cited test is gone.
"""

import re
import subprocess
import sys
from collections import Counter
from functools import cache
from pathlib import Path

from core.harness import EXPECTED_FAILING, FAILED, FLAG_TO_REMOVE, NOT_AUTOMATED, PASSED, evaluate, evaluate_stranger

ROOT = Path(__file__).resolve().parent.parent
ASSESSMENT = ROOT / "docs" / "self_assessment.md"
REFERENCE = ROOT / "docs" / "technical-reference.md"
STRANGER = ROOT / "docs" / "stranger_test.md"
CITED_TEST = re.compile(r"`(tests/test_\w+\.py)::(test_\w+)`")
BREAK_ID = re.compile(r"\b[A-Z]2?-B\d\b")
NUMBER_WORDS = {word: number for number, word in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split())}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end, text.index(start))]


@cache
def _results():
    return evaluate(), evaluate_stranger()


def attack_sentence() -> str:
    attacks = [result for result in _results()[0] if result.suite == "attacks"]
    counts = Counter(result.status for result in attacks)
    missing = [result.id for result in attacks if result.status == NOT_AUTOMATED]
    return (
        f"Of the {len(attacks)} attacks in `suites/attacks.yaml`, {counts[PASSED]} pass, {counts[FAILED]} fail and "
        f"{len(missing)} is not automated. The one not automated is {', '.join(missing)},"
    )


def evidence_line() -> str:
    results, stranger = _results()
    counts = Counter(result.status for result in results)
    strange = Counter(result.status for result in stranger)
    return (
        f"{counts[PASSED]} passed, {counts[FAILED]} failed, {counts[NOT_AUTOMATED]} not automated; stranger runs: "
        f"{strange[PASSED]} passed, {strange[EXPECTED_FAILING]} expected failing, {strange[FAILED]} failed, "
        f"{strange[FLAG_TO_REMOVE]} passes but flagged"
    )


def held_sentence() -> str:
    held = _between(_text(REFERENCE), "### Attempts that held", "### Claimed breaks the skeptics refuted")
    counts = {block.split(",")[0]: len(re.findall(r"^\d+\. ", block, re.M)) for block in re.split(r"\n#### ", held)[1:]}
    listed = ", ".join(f"{attack} {count}" for attack, count in counts.items())
    return f"{sum(counts.values())} attempts held, across all {len(counts)} attack ids: {listed}."


def refuted_sentence() -> str:
    refuted = _between(_text(REFERENCE), "### Claimed breaks the skeptics refuted", "\n## Commit history")
    items = re.findall(r"^\d+\. (.*)$", refuted, re.M)
    breaks = sum(len(BREAK_ID.findall(item.split(":")[0])) for item in items)
    return f"The skeptics' list holds {len(items)} entries naming {breaks} claimed breaks."


def confirmed_sentence() -> str:
    review = _between(_text(REFERENCE), "## Attacks attempted and held", "### Attempts that held")
    word = re.search(r"(\w+) were confirmed and fixed in pull requests 27 to 30", review)
    assert word, "the technical reference no longer says how many breaks were confirmed"
    return f"{NUMBER_WORDS[word[1].lower()]} breaks were confirmed and fixed:"


def verdict_sentence() -> str:
    table = _between(_text(STRANGER), "### Verdicts", "### The twenty tasks")
    verdicts = Counter(row.split("|")[4].strip() for row in table.splitlines() if re.match(r"\| T\d\d \|", row))
    return (
        f"The verdicts were worked {verdicts['Worked']}, worked badly {verdicts['Worked badly']}, "
        f"failed {verdicts['Failed']}, out of {sum(verdicts.values())}."
    )


def after_fixes_sentence() -> str:
    stranger = _results()[1]
    strange = Counter(result.status for result in stranger)
    return f"After the fixes, {strange[PASSED]} of those {len(stranger)} pass and {strange[EXPECTED_FAILING]} is still expected failing"


def collected_sentence() -> str:
    output = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    collected = re.search(r"^(\d+) tests? collected", output, re.M)
    assert collected, output[-500:]
    return f"`pytest` collects {collected[1]} tests"


def test_the_attack_suite_numbers_are_the_harness_numbers():
    assert attack_sentence() in _text(ASSESSMENT)


def test_the_evidence_line_is_what_make_evidence_prints():
    assert evidence_line() in _text(ASSESSMENT)


def test_the_attempts_that_held_are_counted_from_the_technical_reference():
    assert held_sentence() in _text(ASSESSMENT)


def test_the_refuted_breaks_are_counted_from_the_technical_reference():
    assert refuted_sentence() in _text(ASSESSMENT)


def test_the_confirmed_breaks_are_counted_from_the_decisions_and_each_is_listed():
    text = _text(ASSESSMENT)
    sentence = confirmed_sentence()
    assert sentence in text
    listed = _between(text, sentence, "## The stranger test")
    assert len(re.findall(r"^\d+\. ", listed, re.M)) == int(sentence.split()[0])


def test_the_stranger_verdicts_are_counted_from_the_stranger_test():
    assert verdict_sentence() in _text(ASSESSMENT)


def test_the_stranger_runs_after_the_fixes_are_the_harness_numbers():
    assert after_fixes_sentence() in _text(ASSESSMENT)


def test_the_test_count_is_what_pytest_collects():
    assert collected_sentence() in _text(ASSESSMENT)


def test_every_cited_test_exists():
    cited = set(CITED_TEST.findall(_text(ASSESSMENT)))
    assert cited
    missing = [
        f"{path}::{name}" for path, name in sorted(cited)
        if not re.search(rf"^def {name}\(", _text(ROOT / path), re.M)
    ]
    assert missing == []
