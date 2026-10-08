import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WALKTHROUGH = ROOT / "docs" / "code-walkthrough.md"
# A heading that names a Python file sets the file the excerpts under it are copied from, until the
# next second level heading.
FILE_HEADING = re.compile(r"^#{2,4} .*`(?P<path>[\w/.]+\.py)`")


def excerpts() -> list[tuple[str, int, str]]:
    """Every Python excerpt in the walkthrough, with the file it names and the line it starts on."""
    found: list[tuple[str, int, str]] = []
    current: str | None = None
    block: list[str] | None = None
    start = 0
    for number, line in enumerate(WALKTHROUGH.read_text(encoding="utf-8").splitlines(), start=1):
        if block is not None:
            if line.startswith("```"):
                if current is not None:
                    found.append((current, start, "\n".join(block)))
                block = None
            else:
                block.append(line)
            continue
        heading = FILE_HEADING.match(line)
        if heading:
            current = heading["path"]
        elif line.startswith("## "):
            current = None
        elif line.startswith("```python"):
            block, start = [], number
    return found


def test_the_walkthrough_has_excerpts_to_check():
    assert len(excerpts()) > 100


def test_every_python_excerpt_is_copied_exactly_from_the_file_it_names():
    stale = [
        f"line {start}: {path}: {text.splitlines()[0]!r}"
        for path, start, text in excerpts()
        if text not in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert stale == []


def test_the_walkthrough_covers_the_rescue():
    files = {path for path, _, _ in excerpts()}
    text = WALKTHROUGH.read_text(encoding="utf-8")

    assert {"core/rescue.py", "rails/knowledge/loader.py"} <= files
    for name in ("def rescue_start", "def rescue_step", "def _run_on", "def _family_notice", "def _rebuild_rescue"):
        assert any(name in excerpt for path, _, excerpt in excerpts() if path == "core/agent.py"), name
    assert "MAX_IDENTITY_ATTEMPTS" in text


def test_the_walkthrough_covers_the_simulated_rails():
    files = {path for path, _, _ in excerpts()}

    assert {
        "rails/sim/base.py",
        "rails/sim/rules.py",
        "rails/sim/upi_paynow.py",
        "rails/sim/pix.py",
        "rails/sim/cn_bank_remit.py",
        "rails/inbound.py",
    } <= files


YAML_HEADING = re.compile(r"^#{2,4} .*`(?P<path>[\w/.]+\.yaml)`")


def yaml_excerpts() -> list[tuple[str, int, str]]:
    """Every YAML excerpt under a heading that names a YAML file, with the file and the line it starts on."""
    found: list[tuple[str, int, str]] = []
    current: str | None = None
    block: list[str] | None = None
    start = 0
    for number, line in enumerate(WALKTHROUGH.read_text(encoding="utf-8").splitlines(), start=1):
        if block is not None:
            if line.startswith("```"):
                if current is not None:
                    found.append((current, start, "\n".join(block)))
                block = None
            else:
                block.append(line)
            continue
        heading = YAML_HEADING.match(line)
        if heading:
            current = heading["path"]
        elif line.startswith("#"):
            current = None
        elif line.startswith("```yaml"):
            block, start = [], number
    return found


STAGE_8A_FILES = {
    "tests/test_reply_guard.py",
    "tests/test_precheck_china.py",
    "tests/test_plan_update.py",
    "tests/test_attack_one.py",
    "tests/test_attack_two.py",
}
STAGE_8A_YAML = {
    "rails/knowledge/providers.yaml",
    "suites/scenarios/X10.yaml",
    "suites/scenarios/X27.yaml",
    "suites/scenarios/X28.yaml",
    "suites/scenarios/T37.yaml",
    "suites/scenarios/T38.yaml",
}


def test_the_walkthrough_covers_stage_8a():
    files = {path for path, _, _ in excerpts()}
    agent = [excerpt for path, _, excerpt in excerpts() if path == "core/agent.py"]

    assert STAGE_8A_FILES <= files
    assert STAGE_8A_YAML <= {path for path, _, _ in yaml_excerpts()}
    for name in (
        "def _guarded",
        "CARD_NUMBER = ",
        "def _canonical_precheck",
        "def _sender_items",
        "def _after_precheck",
        "def _untrusted_plan_update",
        "def _update_plan",
        "def _skipped_fields",
    ):
        assert any(name in excerpt for excerpt in agent), name
    text = WALKTHROUGH.read_text(encoding="utf-8")
    for heading in ("The reply guard, `core/agent.py`", "The precheck argument mapping, `core/agent.py`", "Updating the plan, `core/agent.py`"):
        assert f"### {heading}" in text, heading


def test_every_yaml_excerpt_under_a_yaml_heading_is_copied_exactly():
    stale = [
        f"line {start}: {path}: {text.splitlines()[0]!r}"
        for path, start, text in yaml_excerpts()
        if text not in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert stale == []


def test_the_walkthrough_covers_stage_8b():
    files = {path for path, _, _ in excerpts()}
    agent = [excerpt for path, _, excerpt in excerpts() if path == "core/agent.py"]

    assert {"core/monthly.py", "tests/test_cancel.py", "tests/test_monthly.py", "tests/test_parent.py"} <= files
    assert {
        "fixtures/demo_parent.yaml",
        "suites/scenarios/T26.yaml",
        "suites/scenarios/T35.yaml",
        "suites/scenarios/T18.yaml",
        "suites/scenarios/T30.yaml",
    } <= {path for path, _, _ in yaml_excerpts()}
    for name in ("def _own_transfer", "def _cancel"):
        assert any(name in excerpt for excerpt in agent), name


def test_the_walkthrough_covers_stage_5b():
    files = {path for path, _, _ in excerpts()}
    text = WALKTHROUGH.read_text(encoding="utf-8")

    assert {"core/anchor_fisco.py", "core/fisco_tx.py", "core/evm_tx.py"} <= files
    assert "## The evidence contract, `chain/LifelineEvidence.sol`" in text
    assert "test_the_factory_says_fisco_is_not_configured_yet" not in text
