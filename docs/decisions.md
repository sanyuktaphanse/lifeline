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
