# 14 September 2026

## What I did

I built the mandate engine rules R01 to R11 with tests, built the hash chained ledger, and put the repo on GitHub with CI.

I built the mandate engine in `core/mandate.py`, the gatekeeper that every money moving action has to pass before anything happens. Here is what it does, in order.

It starts by looking up the tier of the action. Tiers say how dangerous an action is. T0 is reading a balance, T1 is setting a reminder, T2 is moving money or adding a payee or freezing a card, and T3 is changing a limit, changing the mandate, or exporting credentials. The tier is a lookup in `core/tiers.py`, not a judgement call.

The first real check is R01. If the action did not come from the user's own turn, it is refused immediately and nothing else is evaluated. Pasted text, tool results, translated messages, and provider status pages are data. They can be read, but they can never ask for an action.

Then R02 refuses anything at tier T3. A mandate cannot authorise changing itself or raising its own limit or exporting credentials, because a permission slip that can rewrite its own terms is not a permission slip. Only the user can approve those, directly.

Then R03 checks that the mandate is inside its validity window at the moment the action was requested. Tier T0 is exempt, so an expired mandate never stops the student from reading their own balance.

Everything after that applies only to transfers. R10 comes first. If the idempotency key already appears in the history, this exact payment already went out, so the engine stops there and reports only the replay. Evaluating the money rules on a payment that already happened would produce a wrong answer, because the history already contains it.

Then come the five mandate rules, all the same shape. R04 compares the currency to the mandate currency. R06 checks the payee is on the allowed list. R05 checks the corridor is on the allowed list. R07 checks the purpose is on the allowed list. R08 compares the amount to the per transaction limit. Each one that fails adds a rule id and a plain sentence, and none of them stop the others from running, so a transfer that breaks three rules reports all three at once.

R09 is the daily limit. It adds up every transfer in the history that happened on the same calendar day in UTC, adds the amount now being requested, and compares the running total to the daily limit. The reason states the running total, so the refusal says 2,600 against 2,500 instead of just saying no.

R11 is the confirmation token. A clean transfer with no token comes back allowed but marked as needing confirmation, carrying a token and a warning key. The token is an HMAC over the user id, the action type, the idempotency key, the amount, the currency, the corridor, the payee, and the purpose. When the student says yes, the same action is sent again with that token and it goes through. If anything about the payment changed in between, the token no longer matches and R11 refuses it. That is what stops an approval for 1,200 being reused for 1,300.

At the end the engine returns one `Decision` carrying the verdict, every reason, every rule id, the tier, and the confirmation fields. The whole file is plain Python with no model calls, so the same action and the same mandate always produce the same answer.

I also built `core/ledger.py`, a hash chained ledger. Each entry hashes its own contents together with the hash of the entry before it, so the entries are welded in order. Editing an old entry breaks the chain, and recomputing that entry's hash only moves the break to the next entry, which is the property that makes the audit trail worth something.

## What I learned

A rule is not a number, because the limit lives in the mandate. Tests come before code. The token binds a confirmation to one exact action.

Writing the test before the code changed how I thought about each rule. The test forced me to say exactly what should happen before I had any way to make it happen, so the rule id and the refusal became the specification instead of an afterthought.

Every rule turned out to have the same shape. Look at one field on the action, compare it to one field on the mandate, and if they disagree record a rule id and a reason. R04 compares the currency, R05 compares the corridor, R06 compares the payee, R07 compares the purpose, and R08 compares the amount against the per transaction limit.

The engine collects every broken rule instead of stopping at the first one. A transfer that goes to an unknown payee and is also over the limit comes back with both R06 and R08, so the student sees the whole picture in one refusal rather than fixing one problem and running into the next.

The happy path test mattered more than I expected. Five refusal tests only prove the engine can say no. A wall that blocks everything would pass all five. The sixth test is the one that proves the engine still lets a legitimate rent payment through.

The engine is plain Python with no model calls, so the same action and the same mandate always produce the same decision. That is what makes it something to trust with money.

## What is next

Next I build the suites, the interfaces, and the model adapter, and kickoff is on Wednesday.
