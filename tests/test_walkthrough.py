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
