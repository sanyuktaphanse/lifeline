import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from contracts.interfaces import Anchor
from contracts.schemas import Mandate, Message, Role, ToolCall
from core.agent import AgentLoop
from core.anchor_local import ANCHOR_SECRET_VAR, LocalSignedAnchor, user_hash_of
from core.fake_adapter import FakeModelAdapter
from core.ledger import HashChainLedger, JsonlLedger
from core.mandate import DeterministicMandateEngine
from rails.fake_rail import FakeRail
from rails.fake_router import FakeRouter

USER = "student_001"
SECRET = "anchor-loop-secret-0123456789"
RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}
RENT_REQUEST = "Send 1,200 SGD rent to landlord_sp in Brazil"
# The anchor entry carries the student, the turn and the mandate like every entry, and the four anchor values.
ANCHOR_FIELDS = {"user_id", "turn", "mandate_id", "head_hash", "head_seq", "anchor_id", "anchored_at"}


@pytest.fixture(autouse=True)
def anchor_secret(monkeypatch):
    monkeypatch.setenv(ANCHOR_SECRET_VAR, SECRET)
    monkeypatch.delenv("LIFELINE_ENV", raising=False)


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class BrokenAnchor(Anchor):
    def anchor(self, head_hash: str, seq: int, user_hash: str) -> str:
        raise OSError("the anchor store is full")

    def verify(self, head_hash: str) -> bool:
        raise OSError("the anchor store is full")


def _mandate() -> Mandate:
    now = datetime.now(timezone.utc)
    return Mandate(
        id="mandate-student_001-v1",
        user_id=USER,
        currency="SGD",
        per_txn_limit=Decimal("1500"),
        daily_limit=Decimal("2500"),
        allowed_payees={"landlord_sp"},
        allowed_corridors={"SG>BR"},
        allowed_purposes={"rent"},
        valid_from=now - timedelta(days=30),
        valid_until=now + timedelta(days=30),
    )


def _call(name: str, arguments: dict) -> Message:
    return Message(
        role=Role.ASSISTANT,
        text="",
        tool_calls=[ToolCall(id="toolu_01", name=name, arguments=arguments)],
        provider="fake",
        model="fake-model",
    )


def _say(text: str) -> Message:
    return Message(role=Role.ASSISTANT, text=text, provider="fake", model="fake-model")


def _user(text: str) -> Message:
    return Message(role=Role.USER, text=text)


def _loop(responses, tmp_path, *, ledger=None, anchor=None, clock=None) -> tuple[AgentLoop, FakeModelAdapter]:
    adapter = FakeModelAdapter(list(responses))
    loop = AgentLoop(
        adapter=adapter,
        engine=DeterministicMandateEngine(),
        ledger=HashChainLedger() if ledger is None else ledger,
        router=FakeRouter(),
        rails={
            "wise": FakeRail(name="wise", simulated=False),
            "bank_wire": FakeRail(name="bank_wire", simulated=False),
        },
        mandates={USER: _mandate()},
        balances={USER: {"SGD": Decimal("2300")}},
        pending={},
        anchor=LocalSignedAnchor(tmp_path / "anchors.jsonl") if anchor is None else anchor,
        clock=Clock() if clock is None else clock,
    )
    return loop, adapter


def _pay_rent(loop: AgentLoop) -> None:
    token = loop.handle(USER, _user(RENT_REQUEST)).confirmation.confirmation_token
    reply = loop.handle(USER, _user("Yes, send it"), confirmation_token=token)
    assert reply.receipt is not None


def _anchors(ledger) -> list:
    return [entry for entry in ledger.entries() if entry.kind == "anchor"]


def _read_balance(loop: AgentLoop) -> None:
    loop.handle(USER, _user("What is my balance?"))


def test_a_t2_execution_is_anchored_once_after_its_trail(tmp_path):
    ledger = HashChainLedger()
    loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=ledger)

    _pay_rent(loop)

    kinds = [entry.kind for entry in ledger.entries()]
    assert kinds.count("anchor") == 1
    # The proposal turn wrote nothing to anchor; the confirmation's trail is anchored after its last entry.
    assert kinds[-1] == "anchor"
    assert kinds.index("receipt") < kinds.index("anchor")


def test_a_t0_read_writes_no_anchor(tmp_path):
    ledger = HashChainLedger()
    loop, _ = _loop([_call("read_balance", {}), _say("You have 2300 SGD.")], tmp_path, ledger=ledger)

    _read_balance(loop)

    assert [entry.kind for entry in ledger.entries()] == ["proposal", "decision", "execution", "turn"]
    assert not (tmp_path / "anchors.jsonl").exists()


def test_the_anchored_head_is_the_head_before_the_anchor_entry(tmp_path):
    ledger = HashChainLedger()
    loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=ledger)

    _pay_rent(loop)

    entries = ledger.entries()
    [entry] = _anchors(ledger)
    before = entries[entry.seq - 2]
    assert entry.payload["head_seq"] == before.seq == entry.seq - 1
    assert entry.payload["head_hash"] == before.hash == entry.prev_hash
    assert ledger.verify() is None


def test_the_anchor_entry_holds_the_student_the_head_the_sequence_the_id_and_the_time(tmp_path):
    ledger = HashChainLedger()
    clock = Clock()
    anchor = LocalSignedAnchor(tmp_path / "anchors.jsonl", clock=clock)
    loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=ledger, anchor=anchor, clock=clock)

    _pay_rent(loop)

    [entry] = _anchors(ledger)
    assert set(entry.payload) == ANCHOR_FIELDS
    assert entry.payload["user_id"] == USER
    assert entry.payload["anchor_id"].startswith("local:")
    assert datetime.fromisoformat(entry.payload["anchored_at"]) == clock.now
    [line] = [json.loads(line) for line in anchor.path.read_text(encoding="utf-8").splitlines()]
    assert line["head_hash"] == entry.payload["head_hash"]
    assert line["seq"] == entry.payload["head_seq"]
    assert line["user_hash"] == user_hash_of(USER)
    assert line["user_hash"] != hashlib.sha256(USER.encode("utf-8")).hexdigest()
    assert anchor.verify(entry.payload["head_hash"]) is True


def test_nothing_about_money_reaches_an_anchor_line_or_entry_and_the_student_only_the_entry(tmp_path):
    ledger = HashChainLedger()
    loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=ledger)

    _pay_rent(loop)

    [entry] = _anchors(ledger)
    raw = (tmp_path / "anchors.jsonl").read_text(encoding="utf-8")
    line = json.loads(raw)
    # The fields are checked by name, because a random hash or the microseconds of a time can hold "1200" by
    # chance: a hash or a time field must match its strict form, which has no room for a money detail, and
    # every other field must not hold one. Pinning the field names means a new field cannot slip past.
    assert set(entry.payload) == {"user_id", "turn", "mandate_id", "head_hash", "head_seq", "anchor_id", "anchored_at"}
    assert set(line) == {"head_hash", "seq", "user_hash", "anchored_at", "signature"}
    for record, hashes in ((entry.payload, ("head_hash",)), (line, ("head_hash", "user_hash", "signature"))):
        for name in hashes:
            assert re.fullmatch(r"[0-9a-f]{64}", record[name])
        datetime.fromisoformat(record["anchored_at"])
    assert re.fullmatch(r"local:[0-9a-f]{32}", entry.payload["anchor_id"])
    rest = [
        {name: value for name, value in entry.payload.items() if name not in ("head_hash", "anchor_id", "anchored_at")},
        {name: value for name, value in line.items() if name not in ("head_hash", "user_hash", "signature", "anchored_at")},
    ]
    for record in rest:
        for detail in ("1200", "2300", "landlord_sp", "SGD", "rent", "wise"):
            assert detail not in json.dumps(record)
    # The line outside the ledger holds only a hash of the student's id, never the id.
    assert USER not in raw


def test_an_hourly_anchor_fires_when_the_last_anchor_is_older_than_an_hour_and_not_before(tmp_path):
    ledger = HashChainLedger()
    clock = Clock()
    responses = [_call("propose_transfer", RENT), _call("read_balance", {}), _say("2300 SGD."), _call("read_balance", {}), _say("2300 SGD.")]
    loop, _ = _loop(responses, tmp_path, ledger=ledger, clock=clock)
    _pay_rent(loop)
    first = clock.now

    clock.now = first + timedelta(minutes=59)
    _read_balance(loop)
    assert len(_anchors(ledger)) == 1

    clock.now = first + timedelta(minutes=61)
    _read_balance(loop)
    latest = _anchors(ledger)[-1]
    assert len(_anchors(ledger)) == 2
    assert datetime.fromisoformat(latest.payload["anchored_at"]) == clock.now
    assert latest.seq == len(ledger.entries())


def test_with_no_anchor_yet_the_hour_is_measured_from_the_first_entry(tmp_path):
    ledger = HashChainLedger()
    clock = Clock()
    loop, _ = _loop([_call("read_balance", {}), _say("2300 SGD."), _call("read_balance", {}), _say("2300 SGD.")], tmp_path, ledger=ledger, clock=clock)
    _read_balance(loop)
    first = ledger.entries()[0].ts
    assert _anchors(ledger) == []

    clock.now = first + timedelta(minutes=61)
    _read_balance(loop)

    assert len(_anchors(ledger)) == 1


def test_a_restart_rebuilds_the_last_anchor_time_from_the_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    clock = Clock()
    first_loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=JsonlLedger(path), clock=clock)
    _pay_rent(first_loop)
    anchored = clock.now

    soon = Clock()
    soon.now = anchored + timedelta(minutes=30)
    restarted, _ = _loop([_call("read_balance", {}), _say("2300 SGD.")], tmp_path, ledger=JsonlLedger(path), clock=soon)
    _read_balance(restarted)
    assert len(_anchors(JsonlLedger(path))) == 1

    later = Clock()
    later.now = anchored + timedelta(minutes=61)
    again, _ = _loop([_call("read_balance", {}), _say("2300 SGD.")], tmp_path, ledger=JsonlLedger(path), clock=later)
    _read_balance(again)
    assert len(_anchors(JsonlLedger(path))) == 2
    assert JsonlLedger(path).verify() is None


def test_a_failing_anchor_store_writes_a_note_and_the_payment_still_goes_through(tmp_path):
    ledger = HashChainLedger()
    loop, _ = _loop([_call("propose_transfer", RENT)], tmp_path, ledger=ledger, anchor=BrokenAnchor())

    _pay_rent(loop)

    kinds = [entry.kind for entry in ledger.entries()]
    assert "receipt" in kinds
    assert "anchor" not in kinds
    [note] = [e for e in ledger.entries() if e.kind == "note" and e.payload.get("kind") == "anchor_failed"]
    assert note.payload["error"] == "OSError: the anchor store is full"
    assert ledger.verify() is None


def test_a_loop_without_an_anchor_writes_no_anchor(tmp_path):
    ledger = HashChainLedger()
    adapter = FakeModelAdapter([_call("propose_transfer", RENT)])
    loop = AgentLoop(
        adapter=adapter,
        engine=DeterministicMandateEngine(),
        ledger=ledger,
        router=FakeRouter(),
        rails={"wise": FakeRail(name="wise", simulated=False)},
        mandates={USER: _mandate()},
        balances={USER: {}},
        pending={},
    )

    _pay_rent(loop)

    assert "anchor" not in [entry.kind for entry in ledger.entries()]


def _tool_result(adapter: FakeModelAdapter) -> dict:
    tool_message = adapter.calls[-1][0][-1]
    assert tool_message.role is Role.TOOL
    return json.loads(tool_message.text)


def test_verify_ledger_is_a_t0_tool_written_as_proposal_decision_execution(tmp_path):
    ledger = HashChainLedger()
    loop, adapter = _loop([_call("verify_ledger", {}), _say("Your ledger is intact.")], tmp_path, ledger=ledger)

    loop.handle(USER, _user("Show today's ledger and verify it"))

    trail = [entry for entry in ledger.entries() if entry.kind != "turn"]
    assert [entry.kind for entry in trail] == ["proposal", "decision", "execution"]
    assert trail[1].payload["decision"]["tier"] == "T0"
    assert trail[1].payload["decision"]["allowed"] is True
    assert trail[2].payload["action"]["type"] == "verify_ledger"
    result = _tool_result(adapter)["ledger"]
    assert result["first_broken_seq"] is None
    assert result["anchor"] == {"anchored": False, "kind": "local"}
    assert [entry["kind"] for entry in result["entries"]] == ["proposal", "decision"]


def test_verify_ledger_reports_the_latest_anchor_and_that_it_verifies(tmp_path):
    ledger = HashChainLedger()
    clock = Clock()
    anchor = LocalSignedAnchor(tmp_path / "anchors.jsonl", clock=clock)
    responses = [_call("propose_transfer", RENT), _call("verify_ledger", {}), _say("Intact and anchored.")]
    loop, adapter = _loop(responses, tmp_path, ledger=ledger, anchor=anchor, clock=clock)
    _pay_rent(loop)
    [anchored] = _anchors(ledger)

    loop.handle(USER, _user("Show today's ledger and verify it"))

    report = _tool_result(adapter)["ledger"]
    assert report["first_broken_seq"] is None
    assert report["anchor"] == {
        "anchored": True,
        "head_hash": anchored.payload["head_hash"],
        "head_seq": anchored.payload["head_seq"],
        "verified": True,
        "matches_ledger": True,
        "anchored_at": clock.now.isoformat(),
        "kind": "local",
    }
    kinds = [entry["kind"] for entry in report["entries"]]
    # The anchor entry carries the student, so today's entries list it right after the payment's turn.
    assert kinds.index("receipt") < kinds.index("anchor")
    assert len(_anchors(ledger)) == 1
    assert SECRET not in json.dumps(report)
    assert SECRET not in json.dumps([entry.payload for entry in ledger.entries()])


def test_verify_ledger_lists_only_today_and_only_this_student(tmp_path):
    ledger = HashChainLedger()
    ledger.append("agent", "note", {"user_id": USER, "turn": 1, "kind": "x"})
    ledger.append("agent", "note", {"user_id": "someone_else", "turn": 1, "kind": "x"})
    loop, adapter = _loop([_call("verify_ledger", {}), _say("Done.")], tmp_path, ledger=ledger)
    # The student's entry is moved to yesterday straight in the chain, the way tests/test_ledger.py
    # reaches it, so the chain also breaks there.
    ledger._entries[0].ts -= timedelta(days=1)

    loop.handle(USER, _user("Show today's ledger"))

    report = _tool_result(adapter)["ledger"]
    assert [entry["seq"] for entry in report["entries"]] == [3, 4]
    assert report["first_broken_seq"] == 1
