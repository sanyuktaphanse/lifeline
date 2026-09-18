import json

from contracts.schemas import Message, Role, Source
from core.conversation_store import ConversationStore


def _messages(text: str) -> list[Message]:
    return [Message(role=Role.USER, text=text), Message(role=Role.ASSISTANT, text=f"Answer to {text}")]


def test_a_file_store_appends_one_line_per_turn_and_reloads(tmp_path):
    path = tmp_path / "data" / "conversations.jsonl"
    store = ConversationStore(path)
    store.append("student_001", 1, _messages("first"))
    store.append("student_002", 1, _messages("other"))
    store.append("student_001", 2, _messages("second"))

    reloaded = ConversationStore(path)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    assert [m.text for m in reloaded.messages("student_001")] == ["first", "Answer to first", "second", "Answer to second"]
    assert reloaded.users() == {"student_001", "student_002"}


def test_only_the_remembered_fields_are_stored(tmp_path):
    store = ConversationStore(tmp_path / "c.jsonl")
    message = Message(role=Role.ASSISTANT, text="Hi", provider="anthropic", model="claude", provider_content=[{"type": "thinking"}])

    store.append("student_001", 1, [message])

    line = json.loads((tmp_path / "c.jsonl").read_text(encoding="utf-8"))
    assert set(line["messages"][0]) == {"role", "text", "lang", "source", "tool_calls", "tool_call_id"}


def test_erase_removes_one_students_lines_from_the_file_and_memory(tmp_path):
    path = tmp_path / "c.jsonl"
    store = ConversationStore(path)
    store.append("student_001", 1, _messages("mine"))
    store.append("student_002", 1, _messages("theirs"))
    store.append("student_001", 2, _messages("mine again"))

    removed = store.erase("student_001")

    assert removed == 2
    assert store.messages("student_001") == []
    assert "mine" not in path.read_text(encoding="utf-8")
    assert [m.text for m in ConversationStore(path).messages("student_002")] == ["theirs", "Answer to theirs"]
    assert not list(tmp_path.glob("*.tmp"))


def test_an_in_memory_store_writes_nothing(tmp_path):
    store = ConversationStore()
    store.append("student_001", 1, _messages("hello"))

    assert [m.source for m in store.messages("student_001")] == [Source.USER_TURN, Source.USER_TURN]
    assert store.erase("nobody") == 0
