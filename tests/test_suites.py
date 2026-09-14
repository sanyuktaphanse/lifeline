from pathlib import Path

import yaml

SUITES_DIR = Path(__file__).resolve().parent.parent / "suites"
TASKS_PATH = SUITES_DIR / "tasks.yaml"
ATTACKS_PATH = SUITES_DIR / "attacks.yaml"
REQUIRED_FIELDS = {"id", "title", "lane", "tier", "langs"}
ATTACK_FIELDS = {"id", "title", "expected"}


def load(path):
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_task_suite_has_35_unique_ids():
    tasks = load(TASKS_PATH)

    assert isinstance(tasks, list)
    ids = [task["id"] for task in tasks]
    assert len(ids) == 35
    assert len(set(ids)) == 35


def test_every_task_has_all_five_fields():
    for task in load(TASKS_PATH):
        missing = REQUIRED_FIELDS - task.keys()
        assert not missing, f"{task.get('id')} is missing {sorted(missing)}"


def test_attack_suite_has_27_unique_ids():
    attacks = load(ATTACKS_PATH)

    assert isinstance(attacks, list)
    ids = [attack["id"] for attack in attacks]
    assert len(ids) == 27
    assert len(set(ids)) == 27


def test_every_attack_has_all_three_fields():
    for attack in load(ATTACKS_PATH):
        missing = ATTACK_FIELDS - attack.keys()
        assert not missing, f"{attack.get('id')} is missing {sorted(missing)}"
