from pathlib import Path
from typing import Any

import yaml

KNOWLEDGE_DIR = Path(__file__).resolve().parent


def load_knowledge(folder: Path = KNOWLEDGE_DIR) -> dict[str, dict[str, Any]]:
    """Every entry in every YAML file of the folder, by its id. An id used twice is an error."""
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            for entry in yaml.safe_load(handle) or []:
                if entry["id"] in entries:
                    raise ValueError(f"Knowledge entry {entry['id']} appears twice; {path.name} repeats it.")
                entries[entry["id"]] = entry
    return entries
