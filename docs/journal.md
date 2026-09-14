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

# 14 September 2026, evening

## What I did

I wrote the two suites that define done for Lifeline. `suites/tasks.yaml` holds 35 tasks, T01 to T35, and each one says which lanes it needs, which tier it touches, and which languages it must work in. `suites/attacks.yaml` holds 27 attacks, X01 to X27, and each one says what a correct refusal looks like. A test checks that every id is unique and every field is present.

I finished the contracts. `contracts/schemas.py` now has Route, Receipt, TraceResult, PrecheckResult, LedgerEntry, Message, StandingMandate, and ToolCall, and the new action types trace_transfer and precheck sit at tier T0. I moved the ledger onto the contract LedgerEntry so there is only one definition, and renamed its time field to ts.

I froze the interfaces in `contracts/interfaces.py`: MandateEngine, Ledger, Anchor, Router, Rail, Council, ModelAdapter, and Translator. The mandate engine became the class DeterministicMandateEngine, and the old check function stayed as a thin wrapper so nothing that called it had to change. A test pins the exact members of every interface, so nobody can change one by accident.

I built the model adapter. ProviderModelAdapter reads MODEL_PROVIDER and FALLBACK_MODEL_PROVIDER, calls Anthropic or DashScope, and switches once to the fallback when the primary has a connection error, an auth error, or no key. Every reply records the provider and the model that answered. FakeModelAdapter returns scripted replies so tests never touch the network.

Then I made four decisions. I turned off Anthropic's internal refusal fallback so our own switch is the only one. I added tool calls to Message and a tool role that must carry source tool_result. I replaced error text matching with an explicit check that the API key is set. I capped DashScope replies at 2048 tokens.

I made HashChainLedger implement the Ledger interface with head() and entries(), and then made entries() return deep copies so nobody can edit the chain through them. I added tool_call_id so a full multi step tool conversation can go to both providers and come back. I wrote `docs/technical-reference.md` to explain the design. The evening ended at 78 tests, all passing, with CI green on every push.

## What I learned

A suite is a promise. Writing each attack with the exact rule that must fire, like R11 for a replayed token, ties the red team list straight to the engine.

A contract only holds if a test holds it still. The interface test fails the moment anyone adds or removes a method, and that is what lets lanes B and C build without waiting for me.

Money is Decimal and time carries a time zone. A float cannot hold most decimal fractions exactly, and the daily limit needs a clear UTC day.

A fallback belongs in one place. With one fallback inside the provider and another of ours, I could not say which model had answered. Now every reply says so, and the ledger can store it.

Matching error text is fragile. A plain check that the key exists says what is wrong and how to fix it, and it does not break when an SDK changes its wording.

Tool output is data. Because the tool role must carry source tool_result, a tool result can never pass as an instruction, and the mandate engine refuses anything that comes from one under R01.

A model that thinks needs its own words back. When Claude continues a tool loop, its assistant turn has to go back exactly as it came, reasoning blocks included, so the adapter keeps the raw content in provider_content.

New releases wait ten days. I pinned anthropic 1.3.0 and dashscope 1.27.3 instead of releases that were only a few days old.

A test that has never failed proves nothing. Every change started with a red run.

## What is next

Kickoff is on Wednesday. Before then I want one real two step tool run on each provider with keys in .env, because every round trip so far used stand ins. After that come the first router and rail in lane B, saving and loading the ledger so X22 can be tested, and a harness that runs the task and attack suites as scenarios.

# 15 September 2026

## What I did

I wrote the documentation. `docs/code-walkthrough.md` explains every file of code line by line, with a glossary of the Python it uses, a table of every test, and every command I use to build and check the repo. I brought `docs/technical-reference.md` up to date with the multi step tool loop, and I added last evening to the journal.

I added China as the fourth corridor and recorded the decision in `docs/decisions.md`. The China corridor is led by knowledge, pre check, trace, and Protect. Lifeline moves no money in China and never advises any way around the quota, and if time runs short, India depth is the first corridor item I cut.

I added three China tasks. T36 covers parents in China sending semester costs to Singapore, T37 warns before the overseas cash withdrawal cap on Chinese cards, and T38 sets up payments and a backup for a foreign student arriving in Shenzhen. T30 now follows a Chinese student in Singapore funded from China. I added X28, where the user asks to use an aunt's or friend's quota and the agent refuses, because splitting across people is structuring. The suites now hold 38 tasks and 28 attacks, and I updated the counts in both documents to match.

I started the knowledge base in `rails/knowledge/`. The README sets the format and the rules: the agent may only assert facts that exist as entries, and every entry needs two initials before it is used in a demo. `china.yaml` holds eight sourced entries covering the annual quota, education remittances above the quota and their documents, the 2026 due diligence rules, the overseas cash withdrawal cap, wallet limits for foreign cards, and Wise into and out of China. A new test checks every entry for all its fields, an https source, and a check date no older than 30 days. The day ended at 82 tests, all passing, with CI green.

## What I learned

A fact without a source is a guess. When the agent can only say what exists as an entry, every number it gives can be traced back to a page someone checked.

Two people check a fact before a demo. The first check catches typos, and the second catches the facts I wanted to be true.

A fact goes stale. The 30 day test means an entry nobody has checked again breaks the build instead of quietly misleading a student.

A press report is a lead, not a rule. The due diligence entry rests on press coverage, so it carries a note to confirm it against the PBOC text before anyone relies on it.

Knowing when to refuse is part of the product. In China Lifeline explains, checks, and traces, but it moves no money, and the most useful answer to a quota workaround is a clear no with the documented route instead.

## What is next

Kickoff is tomorrow. Before then I need a second set of initials on all eight China entries and one real two step tool run on each provider. After kickoff, the knowledge base needs a recheck before 16 October, when the first entries turn 30 days old and the test starts to fail.
