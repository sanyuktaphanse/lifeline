from pathlib import Path

import yaml

TASKS_PATH = Path(__file__).resolve().parent.parent / "suites" / "tasks.yaml"
REQUIRED_FIELDS = {"id", "title", "lane", "tier", "langs"}


def load_tasks():
    with TASKS_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_task_suite_has_35_unique_ids():
    tasks = load_tasks()

    assert isinstance(tasks, list)
    ids = [task["id"] for task in tasks]
    assert len(ids) == 35
    assert len(set(ids)) == 35


def test_every_task_has_all_five_fields():
    for task in load_tasks():
        missing = REQUIRED_FIELDS - task.keys()
        assert not missing, f"{task.get('id')} is missing {sorted(missing)}"
