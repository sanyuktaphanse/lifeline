"""Write the Wise sandbox operation log the submission asks for as execution evidence.

`make evidence-wise` runs it. Every payment goes through Lifeline's own API in process, exactly as a student's
would: a proposal the mandate engine checks, a confirmation with the engine's token, the payment on the Wise sandbox
rail, and every step in a hash chained ledger, which the run verifies at the end. Only the model is scripted, as in
`core/harness.py`, so the run needs no model key. The one call that does not pass the engine moves a sandbox transfer
along Wise's simulated statuses; it moves no money and exists only in Wise's sandbox.

It refuses to start without WISE_SANDBOX_TOKEN, and neither the token nor a confirmation token reaches the log.
The ledger and the conversation store go to `.harness_tmp/`, inside the repository and ignored by git.
Source: docs/hackathon/rules.md, section 5, item 6; CLAUDE.md, rule 1.
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api.main import create_app
from contracts.errors import RailError
from contracts.interfaces import ModelAdapter
from contracts.schemas import Message, Role, ToolCall
from core.model_adapter import environment
from rails.wise_sandbox import SANDBOX_STEP, STATUS_SOURCE, WiseSandboxClient, WiseSandboxConfig

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "wise-sandbox.md"
WORKDIR = ROOT / ".harness_tmp" / "wise-sandbox"
# Fixture: the demo student sends a small emergency allowance to their own Singapore account, the payee, corridor
# and purpose the demo mandate in fixtures/demo_user.yaml allows. Not a figure about Wise.
USER = "student_001"
ALLOWANCE = {"amount": "25", "currency": "SGD", "corridor": "SG>SG", "payee_id": "self_sg", "purpose": "emergency"}
REQUEST = "Send 25 SGD to my own Singapore account, emergency"
# The order Wise's simulation endpoints move a transfer along. Source: STATUS_SOURCE, "Testing transfer statuses".
SIMULATED = ("processing", "funds_converted", "outgoing_payment_sent")


class ScriptedModel(ModelAdapter):
    """The model, scripted: each new student turn gets the next queued tool call, and a tool result gets plain text."""

    def __init__(self) -> None:
        self.queue: list[Message] = []

    def complete(self, messages, tools) -> Message:
        if messages and messages[-1].role is not Role.TOOL and self.queue:
            return self.queue.pop(0)
        return Message(role=Role.ASSISTANT, text="Done.", provider="scripted", model="scripted")


def _call(name: str, arguments: dict[str, Any], number: int) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="",
        tool_calls=[ToolCall(id=f"evidence_{number}", name=name, arguments=arguments)],
        provider="scripted",
        model="scripted",
    )


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run(client: WiseSandboxClient, out: Path, workdir: Path = WORKDIR) -> list[dict[str, Any]]:
    if ALLOWANCE["payee_id"] not in client.config.recipients:
        raise SystemExit(f"No Wise sandbox recipient is set for {ALLOWANCE['payee_id']!r} in WISE_SANDBOX_RECIPIENTS.")
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    model = ScriptedModel()
    app = create_app(
        adapter=model,
        ledger_path=workdir / "ledger.jsonl",
        conversations_path=workdir / "conversations.jsonl",
        tick_seconds=None,
        wise_sandbox=client,
    )
    api = TestClient(app)
    wise_rail = app.state.loop._rails["wise"]
    rows: list[dict[str, Any]] = []

    def log(step: str, detail: str, result: str) -> None:
        rows.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "step": step, "detail": detail, "result": result})

    def ask(text: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        model.queue.append(_call(tool, arguments, len(rows)))
        reply = api.post("/chat", json={"user_id": USER, "text": text}).json()
        decision = reply.get("decision") or {}
        confirmation = reply.get("confirmation") or {}
        route = confirmation.get("selected_route") or {}
        log(
            "propose",
            f"{tool}: {text}",
            f"engine {'allowed' if decision.get('allowed') else 'refused'} under {', '.join(decision.get('rule_ids') or [])}"
            + (f"; route {route.get('rail')}, fee {route.get('fee')}, simulated {route.get('simulated')}, {route.get('rate_source')}" if route else ""),
        )
        return confirmation

    def confirm(confirmation: dict[str, Any]) -> dict[str, Any]:
        reply = api.post("/confirm", json={"user_id": USER, "confirmation_token": confirmation["confirmation_token"]}).json()
        receipt, cancel = reply.get("receipt"), reply.get("cancel")
        if receipt:
            log("confirm", "the student confirms", f"receipt {receipt['receipt_id']}, {receipt['status']}, simulated {receipt['simulated']}")
        elif cancel:
            log("confirm", "the student confirms", f"cancel {cancel['status']}{': ' + cancel['reason'] if cancel.get('reason') else ''}")
        else:
            log("confirm", "the student confirms", "no receipt: " + reply.get("text", "")[:200])
        return reply

    def trace(receipt_id: str) -> None:
        response = api.post("/trace", json={"user_id": USER, "receipt_id": receipt_id})
        if response.status_code != 200:
            log("trace", receipt_id, f"refused {response.status_code}")
            return
        result = response.json()
        log("trace", receipt_id, f"{result['next_steps'][0]} Lifeline reads it as {result['status']}.")

    paid = confirm(ask(REQUEST, "propose_transfer", ALLOWANCE)).get("receipt")
    if paid:
        trace(paid["receipt_id"])
        for status in SIMULATED:
            try:
                wise_rail.simulate(paid["receipt_id"], status)
                log("simulate", f"{paid['receipt_id']} to {status}, sandbox only", "accepted")
            except RailError as error:
                log("simulate", f"{paid['receipt_id']} to {status}, sandbox only", f"refused: {error}")
            trace(paid["receipt_id"])
    second = confirm(ask(REQUEST, "propose_transfer", ALLOWANCE)).get("receipt")
    if second:
        confirmation = ask(f"Cancel transfer {second['receipt_id']}", "cancel_transfer", {"receipt_id": second["receipt_id"]})
        if confirmation:
            confirm(confirmation)
        log("cancel", second["receipt_id"], "requested through the engine as a T2 action")
        trace(second["receipt_id"])
    verify = api.get(f"/ledger/{USER}/verify").json()
    log("verify", "the ledger's hash chain", f"first broken entry: {verify['first_broken_seq'] or 'none'}")
    _write(out, rows)
    return rows


def _write(out: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Wise sandbox operation log",
        "",
        f"Generated by `rails/wise_sandbox_evidence.py` at {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"from commit `{_commit()}`. {SANDBOX_STEP} Every payment went through Lifeline's API, the mandate engine and a "
        "confirmation, and every step is in the run's hash chained ledger; only the model's tool calls are scripted. "
        f"Wise's statuses are read as described at {STATUS_SOURCE}.",
        "",
        "| Time (UTC) | Step | Detail | Result |",
        "| --- | --- | --- | --- |",
        *(f"| {row['at']} | {row['step']} | {row['detail']} | {str(row['result']).replace('|', '/')} |" for row in rows),
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    config = WiseSandboxConfig.from_env(environment(None))
    if config is None:
        raise SystemExit("The Wise sandbox evidence run needs WISE_SANDBOX_TOKEN in .env; see .env.example.")
    rows = run(WiseSandboxClient(config), args.out)
    print(f"{args.out}: {len(rows)} steps")


if __name__ == "__main__":
    main(sys.argv[1:])
