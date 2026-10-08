import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from contracts.interfaces import Anchor
from core.anchor_local import ANCHOR_SECRET_VAR, AnchorNotConfigured, LocalSignedAnchor, anchor_for

SECRET = "anchor-test-secret-0123456789"
HEAD = "a" * 64
OTHER_HEAD = "b" * 64
USER_HASH = hashlib.sha256(b"student_001").hexdigest()
AT = datetime(2026, 10, 8, 9, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def anchor_secret(monkeypatch):
    monkeypatch.setenv(ANCHOR_SECRET_VAR, SECRET)
    monkeypatch.delenv("LIFELINE_ENV", raising=False)


def _anchor(tmp_path, at: datetime = AT) -> LocalSignedAnchor:
    return LocalSignedAnchor(tmp_path / "data" / "anchors.jsonl", clock=lambda: at)


def _lines(anchor: LocalSignedAnchor) -> list[dict]:
    return [json.loads(line) for line in anchor.path.read_text(encoding="utf-8").splitlines()]


def _rewrite(anchor: LocalSignedAnchor, lines: list[dict]) -> None:
    anchor.path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def test_the_local_anchor_implements_the_anchor_interface(tmp_path):
    assert isinstance(_anchor(tmp_path), Anchor)


def test_an_anchored_head_verifies_and_another_head_does_not(tmp_path):
    anchor = _anchor(tmp_path)

    anchor_id = anchor.anchor(HEAD, 7, USER_HASH)

    assert anchor.verify(HEAD) is True
    assert anchor.verify(OTHER_HEAD) is False
    assert anchor_id
    assert anchor.anchored_at(HEAD) == AT
    assert anchor.anchored_at(OTHER_HEAD) is None


def test_an_anchor_line_holds_the_head_the_sequence_the_user_hash_a_time_and_a_signature(tmp_path):
    anchor = _anchor(tmp_path)

    anchor_id = anchor.anchor(HEAD, 7, USER_HASH)

    [line] = _lines(anchor)
    assert set(line) == {"head_hash", "seq", "user_hash", "anchored_at", "signature"}
    assert (line["head_hash"], line["seq"], line["user_hash"]) == (HEAD, 7, USER_HASH)
    assert datetime.fromisoformat(line["anchored_at"]) == AT
    # The id is derived from the signature, so it names this anchor and no other.
    assert anchor_id == f"local:{line['signature'][:32]}"


def test_each_anchor_appends_one_line(tmp_path):
    anchor = _anchor(tmp_path)

    anchor.anchor(HEAD, 7, USER_HASH)
    anchor.anchor(OTHER_HEAD, 9, USER_HASH)

    assert [line["seq"] for line in _lines(anchor)] == [7, 9]
    assert anchor.verify(HEAD) and anchor.verify(OTHER_HEAD)


@pytest.mark.parametrize(
    "field, value",
    [
        ("head_hash", OTHER_HEAD),
        ("seq", 8),
        ("user_hash", "c" * 64),
        ("anchored_at", (AT + timedelta(seconds=1)).isoformat()),
        ("signature", "0" * 64),
    ],
)
def test_a_line_with_any_field_changed_verifies_false(tmp_path, field, value):
    anchor = _anchor(tmp_path)
    anchor.anchor(HEAD, 7, USER_HASH)
    [line] = _lines(anchor)

    _rewrite(anchor, [{**line, field: value}])

    assert anchor.verify(HEAD) is False
    assert anchor.verify(OTHER_HEAD) is False
    assert anchor.anchored_at(HEAD) is None


def test_a_missing_file_verifies_false(tmp_path):
    anchor = _anchor(tmp_path)

    assert not anchor.path.exists()
    assert anchor.verify(HEAD) is False
    assert anchor.anchored_at(HEAD) is None


def test_a_line_that_is_not_an_anchor_is_passed_over(tmp_path):
    anchor = _anchor(tmp_path)
    anchor.anchor(HEAD, 7, USER_HASH)
    with anchor.path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n[1, 2]\n{\"head_hash\": \"" + OTHER_HEAD + "\"}\n")

    assert anchor.verify(HEAD) is True
    assert anchor.verify(OTHER_HEAD) is False


def test_the_secret_is_read_at_call_time_so_another_secret_verifies_nothing(tmp_path, monkeypatch):
    anchor = _anchor(tmp_path)
    anchor.anchor(HEAD, 7, USER_HASH)

    monkeypatch.setenv(ANCHOR_SECRET_VAR, "a-different-secret")

    assert anchor.verify(HEAD) is False


def test_the_secret_never_appears_in_a_line_or_an_id(tmp_path):
    anchor = _anchor(tmp_path)

    anchor_id = anchor.anchor(HEAD, 7, USER_HASH)

    assert SECRET not in anchor.path.read_text(encoding="utf-8")
    assert SECRET not in anchor_id


def test_production_without_a_secret_raises_at_call_time_without_naming_a_secret(tmp_path, monkeypatch):
    monkeypatch.delenv(ANCHOR_SECRET_VAR)
    monkeypatch.setenv("LIFELINE_ENV", "production")
    anchor = _anchor(tmp_path)

    with pytest.raises(RuntimeError, match=ANCHOR_SECRET_VAR):
        anchor.anchor(HEAD, 7, USER_HASH)
    assert not anchor.path.exists()


def test_an_empty_secret_counts_as_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv(ANCHOR_SECRET_VAR, "")
    monkeypatch.setenv("LIFELINE_ENV", "production")

    with pytest.raises(RuntimeError, match=ANCHOR_SECRET_VAR):
        _anchor(tmp_path).anchor(HEAD, 7, USER_HASH)


@pytest.mark.parametrize(
    "head, seq, user_hash",
    [
        ("1200 SGD to landlord_sp", 7, USER_HASH),
        (HEAD.upper(), 7, USER_HASH),
        (HEAD, 7, "student_001"),
        (HEAD, "7", USER_HASH),
        (HEAD, True, USER_HASH),
        (HEAD, -1, USER_HASH),
    ],
)
def test_an_anchor_takes_only_a_hash_a_sequence_and_a_user_hash(tmp_path, head, seq, user_hash):
    anchor = _anchor(tmp_path)

    with pytest.raises(ValueError):
        anchor.anchor(head, seq, user_hash)
    assert not anchor.path.exists()


def test_the_factory_gives_the_local_anchor_by_default_and_for_local(tmp_path):
    path = tmp_path / "anchors.jsonl"

    for value in ({}, {"ANCHOR": ""}, {"ANCHOR": "local"}, {"ANCHOR": " Local "}):
        anchor = anchor_for(value, path)
        assert isinstance(anchor, LocalSignedAnchor)
        assert anchor.path == path


def test_the_factory_gives_the_fisco_anchor_for_fisco(tmp_path):
    from core.anchor_fisco import FiscoBcosAnchor

    for value in ("fisco", " FISCO "):
        assert isinstance(anchor_for({"ANCHOR": value}, tmp_path / "anchors.jsonl"), FiscoBcosAnchor)


def test_the_factory_names_the_values_it_takes_for_an_unknown_anchor(tmp_path):
    with pytest.raises(ValueError, match="local"):
        anchor_for({"ANCHOR": "ethereum"}, tmp_path / "anchors.jsonl")
