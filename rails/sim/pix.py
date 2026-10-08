"""Simulated Pix, the Brazilian instant payment scheme, on the Singapore to Brazil corridor.

Pix reaches a payee only through a Pix key (br_pix_keys_002) and settles in real time
(br_pix_instant_001). The rail holds the payee ids that have a key on file, never a key itself.
Source: docs/decisions.md, 8 October 2026.
"""

from collections.abc import Iterable

from contracts.schemas import ReceiptStatus, Route
from rails.sim.base import SimRail
from rails.sim.rules import PIX_SCHEME_ENTRY, pix_refusals


class PixSimRail(SimRail):
    NAME = "sim_pix"
    STAGES = (("created", ReceiptStatus.CREATED), ("completed", ReceiptStatus.COMPLETED))
    # No clock: the entry says Pix settles in real time, so a normal transfer is completed at once.
    STAGE_HOURS = 0
    DURATION_ENTRY = PIX_SCHEME_ENTRY

    def __init__(self, pix_key_on_file: Iterable[str] = (), script: str = "normal") -> None:
        super().__init__(script=script)
        self.pix_key_on_file = frozenset(pix_key_on_file)

    def first_status(self) -> ReceiptStatus:
        if self.script == "delayed":
            return ReceiptStatus.CREATED
        return ReceiptStatus.COMPLETED

    def refusals(self, route: Route, mandate_ref: str) -> list[str]:
        return [reason for _, reason in pix_refusals(route.payee_id, self.pix_key_on_file)]
