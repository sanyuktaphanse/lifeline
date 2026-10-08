from pathlib import Path

import core.harness
from core.anchor_local import LocalSignedAnchor
from core.harness import ROOT, run_scenario_run

RENT = {"amount": "1200", "currency": "SGD", "corridor": "SG>BR", "payee_id": "landlord_sp", "purpose": "rent"}

PAID = {
    "id": "T06",
    "expected": {"reply": "receipt", "ledger": ["proposal", "decision", "confirmation", "execution", "receipt"]},
}
PAID_RUN = {
    "lang": "en",
    "turns": [
        {"user": "Send 1,200 SGD rent to landlord_sp", "model": [{"calls": [{"name": "propose_transfer", "arguments": RENT}]}]},
        {"user": "Yes", "confirm": "latest"},
    ],
}


def test_the_harness_gives_the_loop_a_local_anchor_outside_data_and_keeps_anchor_entries_out_of_the_trail(monkeypatch):
    paths: list[Path] = []
    anchored: list[str] = []

    class Recording(LocalSignedAnchor):
        def __init__(self, path: Path, **kwargs) -> None:
            super().__init__(path, **kwargs)
            paths.append(path)

        def anchor(self, head_hash: str, seq: int, user_hash: str) -> str:
            anchor_id = super().anchor(head_hash, seq, user_hash)
            anchored.append(anchor_id)
            assert self.verify(head_hash)
            return anchor_id

    monkeypatch.setattr(core.harness, "LocalSignedAnchor", Recording)

    result = run_scenario_run(PAID, PAID_RUN)

    assert result.failures == []
    assert len(anchored) == 1
    [path] = paths
    assert not path.is_relative_to(ROOT / "data")
    # The run's anchor file is removed with its temporary directory when the run ends.
    assert not path.exists()
