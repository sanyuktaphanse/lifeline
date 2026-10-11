"""Starts the real Lifeline API, as `make dev` does, with its data files in a folder of the test's choosing.

Only the data paths differ from `make dev`: the adapter, the engine, the rails and the fixtures are the real ones,
so /chat answers 503 here exactly as it does without a key in `.env`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from api.main import create_app  # noqa: E402


def main() -> None:
    port, data = int(sys.argv[1]), Path(sys.argv[2])
    data.mkdir(parents=True, exist_ok=True)
    app = create_app(ledger_path=data / "ledger.jsonl", conversations_path=data / "conversations.jsonl")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
