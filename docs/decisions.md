# Decisions

This file records product decisions for Lifeline, newest last, with the date each one was made.

## 14 September 2026

1. China is added as the fourth corridor.
2. The China corridor is led by knowledge, pre check, trace, and Protect.
3. Lifeline moves no money in China, and it never advises any way around the quota.
4. If time runs short, India depth is the first corridor item to be cut.

## 18 September 2026

1. `Action` gains an optional `instrument_id`, and the confirmation token signs it. Task T14 freezes a lost card and task T15 sends the student to the issuer's app when the freeze is not supported. Neither can be built while a token to freeze a card does not say which card.
2. `Mandate` gains `payee_added_at`, the time each payee was added, and `cooling_hours`, the waiting time before a new payee can receive a transfer, 24 hours unless set otherwise. Task T09 adds a payee and tells the student it needs confirmation and a cooling period, which cannot be built without knowing when the payee was added and how long the wait is.
3. Rule R14 refuses a transfer to a payee added less than `cooling_hours` ago, and its reason states when the transfer becomes allowed.
4. `AgentReply` gains an optional `freeze` field holding the `FreezeResult` of a freeze that was executed. Task T15 has to send a student whose issuer does not allow the freeze to the issuer's app. The frontend needs the status and the deep link as data it can turn into a button, not only as words inside the reply text, which it cannot parse reliably in three languages.
5. `Action.amount` has a schema ceiling of one hundred million. No student transfer comes near it, so a larger figure is a mistake or an attack and is rejected before it becomes an action.
6. The agent loop remembers the last twenty messages of each student's conversation, tool results included, and gives them to the model on every call. Twenty covers several turns of tool use while keeping each request small.
7. Standing mandates use the existing `StandingMandate` model. Its `schedule` is written `monthly:D`, with D from 1 to 28 so every month has the day, due at 00:00 UTC on that day; a period is the calendar month of the due date.
8. A standing run may happen from `notice_hours` before the due time until 24 hours after it. `cancel_window_hours` may not exceed `notice_hours`, so a run can happen by the due time, and the cancel window counts from when the notice was actually written, so a student always gets the whole window to cancel.
9. `ActionType` gains `create_standing_mandate` at tier T2 with the warning key `warn.standing.new`, and `cancel_standing_run` at tier T1. `Action` gains `standing_mandate_id` and `standing_terms`, and the confirmation token signs both, so a token for one set of terms is refused for another.
10. `Source` gains `standing_mandate` for runs the agent loop starts on the student's behalf. R01 accepts it only on a transfer whose `standing_mandate_id` names an active standing mandate the student confirmed before the run.
11. Rule R12 allows a transfer within its standing mandate's pattern at tier T1 without confirmation. Rule R13 treats a transfer outside the pattern as an ordinary T2 transfer needing confirmation, and its reason names every part that fell outside. Neither rule lifts the money rules: a run still passes R03 to R09 and R14.
12. A standing mandate's id is the student's id, `standing`, the turn, and the call number, such as `student_001-standing-1-1`, so the loop and never the model chooses it. A run's receipt names the standing mandate id as its `mandate_ref`, because that is the authority the run was paid under.
