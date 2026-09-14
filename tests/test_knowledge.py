from datetime import date, timedelta
from pathlib import Path

import yaml

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "rails" / "knowledge"
ENTRY_FIELDS = {
    "id",
    "statement",
    "country",
    "rail",
    "kind",
    "source_url",
    "source_type",
    "date_checked",
    "checked_by",
    "second_check_by",
    "used_by",
}
MAX_AGE = timedelta(days=30)


def load_entries() -> list[tuple[str, dict]]:
    entries = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            for entry in yaml.safe_load(handle) or []:
                entries.append((path.name, entry))
    return entries


def test_knowledge_base_has_entries():
    assert load_entries()


def test_every_entry_has_all_fields():
    for file_name, entry in load_entries():
        missing = ENTRY_FIELDS - entry.keys()
        assert not missing, f"{file_name} {entry.get('id')} is missing {sorted(missing)}"


def test_every_source_url_uses_https():
    for file_name, entry in load_entries():
        assert str(entry["source_url"]).startswith("https://"), (
            f"{file_name} {entry['id']} has source_url {entry['source_url']}"
        )


def test_no_entry_is_older_than_30_days():
    today = date.today()
    for file_name, entry in load_entries():
        checked = date.fromisoformat(str(entry["date_checked"]))
        assert today - checked <= MAX_AGE, (
            f"{file_name} {entry['id']} was last checked on {checked}"
        )
