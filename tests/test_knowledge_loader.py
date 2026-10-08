import pytest

from rails.knowledge.loader import KNOWLEDGE_DIR, load_knowledge
from tests.test_knowledge import load_entries


def test_every_entry_in_the_folder_is_returned_by_its_id():
    entries = load_knowledge()

    assert set(entries) == {entry["id"] for _, entry in load_entries()}
    assert entries["cn_atm_cap_005"]["country"] == "CN"


def test_the_default_folder_is_the_knowledge_folder():
    assert KNOWLEDGE_DIR.name == "knowledge"
    assert load_knowledge(KNOWLEDGE_DIR) == load_knowledge()


def test_a_folder_without_yaml_files_gives_no_entries(tmp_path):
    (tmp_path / "README.md").write_text("Not an entry.", encoding="utf-8")

    assert load_knowledge(tmp_path) == {}


def test_every_yaml_file_in_the_folder_is_read(tmp_path):
    (tmp_path / "aa.yaml").write_text('- id: aa_one_001\n  statement: "One."\n', encoding="utf-8")
    (tmp_path / "bb.yaml").write_text('- id: bb_two_001\n  statement: "Two."\n', encoding="utf-8")

    assert set(load_knowledge(tmp_path)) == {"aa_one_001", "bb_two_001"}


def test_an_id_used_twice_is_refused(tmp_path):
    (tmp_path / "aa.yaml").write_text('- id: same_001\n  statement: "One."\n', encoding="utf-8")
    (tmp_path / "bb.yaml").write_text('- id: same_001\n  statement: "Two."\n', encoding="utf-8")

    with pytest.raises(ValueError, match="same_001"):
        load_knowledge(tmp_path)


def test_an_empty_file_gives_no_entries(tmp_path):
    (tmp_path / "empty.yaml").write_text("", encoding="utf-8")

    assert load_knowledge(tmp_path) == {}
