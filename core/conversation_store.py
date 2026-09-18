import json
import os
from pathlib import Path
from typing import Any

from contracts.schemas import Message

# The parts of a message the memory keeps. Provider reasoning blocks and model names are left out.
REMEMBERED_FIELDS = {"role", "text", "lang", "source", "tool_calls", "tool_call_id"}


class ConversationStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._records: list[dict[str, Any]] = []
        if path is not None and path.exists():
            with path.open(encoding="utf-8") as handle:
                self._records = [json.loads(line) for line in handle if line.strip()]

    def append(self, user_id: str, turn: int, messages: list[Message]) -> None:
        record = {
            "user_id": user_id,
            "turn": turn,
            "messages": [message.model_dump(mode="json", include=REMEMBERED_FIELDS) for message in messages],
        }
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._records.append(record)

    def records(self, user_id: str) -> list[dict[str, Any]]:
        return [json.loads(json.dumps(record)) for record in self._records if record["user_id"] == user_id]

    def messages(self, user_id: str) -> list[Message]:
        return [Message.model_validate(message) for record in self.records(user_id) for message in record["messages"]]

    def users(self) -> set[str]:
        return {record["user_id"] for record in self._records}

    def erase(self, user_id: str) -> int:
        kept = [record for record in self._records if record["user_id"] != user_id]
        removed = len(self._records) - len(kept)
        if self._path is not None and removed:
            temporary = self._path.with_name(self._path.name + ".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                handle.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in kept)
            os.replace(temporary, self._path)
        self._records = kept
        return removed
