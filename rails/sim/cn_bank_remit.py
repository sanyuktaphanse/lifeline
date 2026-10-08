"""Simulated bank remittance from China to a student in Singapore.

It funds the student's own account, as Bank of China's An Xin account does (cn_boc_anxin_009), and
never pays the institution, which NUS asks to be paid through Flywire or Convera
(sg_nus_fee_payment_003). Lifeline never proposes a transfer on this corridor: no mandate allows it,
and the engine refuses one under R05. Source: docs/decisions.md, 8 October 2026.
"""

from collections.abc import Iterable

from contracts.schemas import ReceiptStatus, Route
from rails.sim.base import SimRail
from rails.sim.rules import CN_FUNDING_ENTRY, CN_QUOTA_ENTRY, cn_documents, cn_purpose_refusals


class CnBankRemitSimRail(SimRail):
    NAME = "cn_bank_remit_sim"
    # The provider's stages in its own words, each mapped onto the ReceiptStatus that fits it.
    STAGES = (
        ("documents submitted", ReceiptStatus.CREATED),
        ("under review", ReceiptStatus.HELD_FOR_REVIEW),
        ("released", ReceiptStatus.FUNDED),
        ("in transit", ReceiptStatus.IN_TRANSIT),
        ("arrived", ReceiptStatus.COMPLETED),
    )
    # Fixture: simulated hours between two stages. No entry gives a duration for this transfer.
    STAGE_HOURS = 48
    DURATION_ENTRY = CN_FUNDING_ENTRY

    def __init__(
        self, documents_on_file: Iterable[str] = (), quota_position_known: bool = False, script: str = "normal"
    ) -> None:
        super().__init__(script=script)
        self.documents_on_file = frozenset(documents_on_file)
        self.quota_position_known = quota_position_known

    def refusals(self, route: Route, mandate_ref: str) -> list[str]:
        refused = [reason for _, reason in cn_purpose_refusals(route.purpose)]
        missing = [document for document in cn_documents() if document not in self.documents_on_file]
        if missing:
            refused.append(
                f"The Bank of China checklist is not complete: {', '.join(missing)} is not on file. "
                f"Source: {CN_FUNDING_ENTRY}."
            )
        if not self.quota_position_known:
            refused.append(
                f"The sender's position against the annual foreign currency quota is not known. Source: {CN_QUOTA_ENTRY}."
            )
        return refused
