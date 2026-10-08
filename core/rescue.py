"""The rescue state machine: its states, its transitions, and each student's current state.

It moves nothing and writes nothing. Every effect of a rescue goes through the agent loop and the
mandate engine like any other action. Source: docs/decisions.md, 8 October 2026.

S0 detect, S1 identity check, S2 freeze, S3 wallet token check, S4 reroute to the backup,
S5 money in hand, S6 no backup, S7 replacement, S8 plan rewrite, S9 family notice.
"""

from contracts.schemas import RescueState as S

START = "start"

TRANSITIONS: dict[tuple[S | None, str], S] = {
    (None, START): S.S0,
    (S.DONE, START): S.S0,
    (S.S0, "detected"): S.S1,
    (S.S1, "identity_verified"): S.S2,
    (S.S2, "freeze_settled"): S.S3,
    (S.S3, "has_backup"): S.S4,
    (S.S3, "no_backup"): S.S6,
    (S.S4, "rerouted"): S.S5,
    (S.S5, "money_settled"): S.S7,
    (S.S6, "cash_listed"): S.S7,
    (S.S7, "replacement_given"): S.S8,
    (S.S8, "standing_stopped"): S.S9,
    (S.S9, "notice_settled"): S.DONE,
}


class RescueMachine:
    def __init__(self) -> None:
        self._states: dict[str, S] = {}

    def state(self, user_id: str) -> S | None:
        return self._states.get(user_id)

    def active(self, user_id: str) -> bool:
        return self.state(user_id) not in (None, S.DONE)

    def start(self, user_id: str) -> tuple[S | None, S]:
        return self.advance(user_id, START)

    def advance(self, user_id: str, event: str) -> tuple[S | None, S]:
        before = self.state(user_id)
        after = TRANSITIONS.get((before, event))
        if after is None:
            name = "no rescue" if before is None else before.value
            raise ValueError(f"A rescue in {name} does not take the event {event!r}.")
        self._states[user_id] = after
        return before, after
