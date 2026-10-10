# Lifeline technical documentation: backend sections

Draft by lane B for item 1 of the submission checklist in `docs/hackathon/requirements.md`: system architecture, core algorithm description, and security design. Lane A owns the full submission document (build program Stage 17); these sections are written to be folded into it. Every statement below describes code on `main` at commit `7a4360e`, 10 October 2026, unless it is marked as in review. Test counts and suite results are from that commit: 1428 tests passed, 3 skipped, 4 expected failures; `make evidence` gave 58 entries passed, 0 failed, 8 not automated.

## 1. System architecture

### 1.1 The design rule

The model proposes. The engine decides. A rail executes. The ledger records. A language model reads the student's message and may propose an action, but it never decides whether money moves: every action passes a deterministic mandate engine written in plain Python, and every proposal, decision, confirmation, execution and receipt is an entry in a hash chained ledger.

### 1.2 Components

| Component | File | What it does | State on `main` |
| --- | --- | --- | --- |
| Contracts | `contracts/schemas.py`, `contracts/interfaces.py` | Every data shape and every interface between lanes, frozen | Implemented |
| Tiers | `core/tiers.py` | Maps each of the 23 action types to a risk tier, T0 to T3 | Implemented |
| Mandate engine | `core/mandate.py` | Allows or refuses every action under rules R01 to R14 and issues confirmation tokens | Implemented, no model calls |
| Agent loop | `core/agent.py` | Turns a student's message into model calls and tool calls, routes every action through the engine, pays on a rail, writes the ledger | Implemented |
| Model adapter | `core/model_adapter.py` | One interface over Anthropic and Alibaba Cloud DashScope, with a fallback provider | Implemented |
| Council | `core/council.py` | Five model voices, cost, speed, safety, rules and timing, and a chair written in code, advising which route carries a large or unusual transfer | Implemented, optional, advisory only |
| Ledger | `core/ledger.py` | Append only, hash chained record, in memory or in a JSON lines file | Implemented |
| Anchor | `core/anchor_local.py`, `core/anchor_fisco.py`, `chain/LifelineEvidence.sol` | Signs the ledger head into a local file, or writes it to a FISCO BCOS chain | Implemented; FISCO BCOS tested on a local four node network |
| Rescue | `core/rescue.py` | The lost card state machine, states S0 to S9 | Implemented |
| Standing mandates and monthly note | `core/standing.py`, `core/monthly.py` | Recurring payments confirmed once, and a monthly summary from the ledger | Implemented |
| Router | `rails/fake_router.py` | Quotes routes per corridor and answers prechecks from the knowledge base | Implemented with fixture fees |
| Rails | `rails/fake_rail.py`, `rails/sim/` | A fixture rail, and simulated Pix, UPI to PayNow and China bank remittance rails with sourced rules | Implemented; all move no money |
| Knowledge base | `rails/knowledge/*.yaml` | Sourced entries: limits, purposes, documents, each with a source address and a check date | Implemented, 18 entries |
| Application programming interface (API) | `api/main.py` | FastAPI server the app calls | Implemented |
| Evaluation harness | `core/harness.py`, `suites/` | Plays the task and attack suites and writes `evidence/report.md` | Implemented |

In review, not on `main`: the Wise sandbox rail and its quotes (`rails/wise_sandbox.py`, pull request 39) and the translator (`rails/translator.py`, pull request 40).

### 1.3 The path of one transfer

1. The student writes, for example, "send my landlord this month's rent". The API passes the text to `AgentLoop.handle` as the student's own turn. Pasted text arrives in a separate field and is marked as pasted, never as the student's turn.
2. The loop calls the model through the adapter with the tool definitions. The model answers with a tool call such as `propose_transfer` with an amount, currency, corridor, payee id and purpose.
3. The loop builds an `Action`. Schema validation rejects a zero, negative or oversized amount, a malformed corridor and a short idempotency key before anything else runs. The loop marks the action's source: a payee, amount or receipt id that first appeared in pasted text or a tool result makes the action data, not an instruction.
4. The loop asks the router for routes. Each route carries its fee, spread, arrival time, status, whether it is simulated, and the knowledge entry it rests on. Blocked routes are returned with their reason, never dropped.
5. The engine checks the action against the student's mandate and the history of executed actions. A transfer is T2, so a clean one comes back allowed but needing confirmation, with a token bound to that exact action and a warning key.
6. When the council is on and a trigger fires, such as an amount above half the per transaction limit, the council advises a route. Its advice is written to the ledger and cannot change the amount, the payee or the token.
7. The student sees the confirmation: amount, payee, rail, every cost line, arrival, simulated or not, and the warning. They confirm by sending the token back within 300 seconds.
8. The engine checks the token again. The loop pays on the chosen rail with the action's idempotency key. When a rail fails, nothing is charged and the student is offered the next usable route under the same token and key, so nothing is paid twice.
9. Proposal, decision, confirmation, execution and receipt are each a ledger entry. After every T2 execution, and at least hourly, the ledger head is anchored.
10. The reply passes a guard that redacts card numbers, issued tokens and secrets, and is returned in the student's language.

## 2. Core algorithm description

### 2.1 Permission tiers

| Tier | Meaning | Action types | How it is enforced |
| --- | --- | --- | --- |
| T0 | Reads and explains, moves nothing | `read_balance`, `trace_transfer`, `precheck`, `get_quote`, `check_wallet_token`, `verify_ledger`, `monthly_summary` | Allowed for the student under R02, valid even under an expired mandate |
| T1 | Low risk, reversible | `set_reminder`, `cancel_standing_run`, `deactivate_standing_mandate`, `rescue_identity_check`, `reroute_to_backup`, `notify_family`, `update_plan`, `record_cash_withdrawal` | Allowed under the mandate without confirmation, logged |
| T2 | Moves money or changes who can receive it | `transfer`, `add_payee`, `freeze_card`, `create_standing_mandate`, `cancel_transfer` | Same turn confirmation with a token bound to the exact action and a risk warning |
| T3 | Changes the rules themselves | `change_limit`, `change_mandate`, `export_credentials` | Always refused in chat |

A transfer within the pattern of a standing mandate the student confirmed is decided at T1 under R12.

### 2.2 The mandate engine

`DeterministicMandateEngine.check(action, mandate, history)` returns a `Decision`: allowed or not, the tier, every reason, and the rule ids. The same inputs always give the same decision. It runs the rules in this order:

| Order | Rule | Checks |
| --- | --- | --- |
| 1 | R01 | The action came from the student's own turn, or is a run of a standing mandate the student confirmed. Otherwise refused at once |
| 2 | R02 | The tier is not T3 |
| 3 | R03 | The mandate is valid at the request time; T0 is exempt |
| 4 | R10 | The idempotency key has not already been executed. Otherwise refused at once |
| 5 | R04 | The action is well formed: an amount and a currency matching the mandate, a payee id in plain characters, a card written `issuer:card` |
| 6 | R06 | The payee is in the allowed payees, matched by exact id, never by display name |
| 7 | R14 | A payee added through Lifeline was added at least 24 hours ago, or the mandate's own cooling period |
| 8 | R05 | The corridor is allowed |
| 9 | R07 | The purpose is allowed |
| 10 | R08 | The amount is within the per transaction limit |
| 11 | R09 | Today's executed total plus this amount is within the daily limit |
| 12 | R11 | A confirmation token, when given, belongs to this exact action |
| 13 | R12, R13 | A transfer naming a standing mandate is within its pattern (R12, lowered to T1) or outside it (R13, escalated to T2) |

R01 and R10 stop evaluation at once: an injected instruction should not be evaluated at all, and a replayed payment would otherwise be counted twice by the money rules. Every other rule collects its failure, so a refusal lists every rule broken. An allowed decision cites the rule that governed it: R02 for T0 and T1, R12 for a standing run, R11 for T2.

### 2.3 The confirmation token

A T2 action without a token is allowed but needs confirmation. The token is an HMAC with SHA 256, under the deployment secret `LIFELINE_CONFIRM_SECRET`, over nine fields: user id, action type, idempotency key, amount, currency, corridor, payee, purpose and card. Changing any field changes the token, so a confirmation for 1,200 SGD cannot pay 1,300, a token for one card cannot freeze another, and a token from an earlier transfer cannot be replayed because its idempotency key differs. Tokens are compared in constant time. A pending confirmation expires after 300 seconds.

### 2.4 Choosing a route

The router returns every route for the corridor. The loop considers only usable routes: not blocked, not down, within limits, and not on a rail that already failed this payment. Among them it prefers routes that are not simulated, and picks the lowest fee plus spread (`_considered` and `_choose` in `core/agent.py`). When the council convenes, its chair, a function and not a model, tallies the five voices' positions weighted by their confidence, and the disagreement score is one minus the share of answering voices that agree with the choice. Above 0.4 the runner up is named to the student.

### 2.5 The hash chained ledger and its anchor

Each entry is hashed with SHA 256 over canonical JSON of its sequence number, time, actor, kind, payload and the previous entry's hash. `verify()` recomputes every hash from the first entry and returns the sequence number of the first broken entry, or none. Editing an entry breaks it; recomputing its hash moves the break to the next entry. To catch a forger who rewrites every later entry, the loop anchors the head hash, its sequence number and a keyed hash of the student id, never the id or any amount, to a local signed file or to the `LifelineEvidence` contract on FISCO BCOS. A ledger that does not verify, or disagrees with the anchor store, puts the loop on an integrity hold: every T2 execution except a card freeze is refused until it is resolved.

### 2.6 The rails layer

Every limit, purpose and document list a simulated rail enforces is read by id from a knowledge entry with a source address, and every refusal names its entry. UPI to PayNow allows only the two purposes the Reserve Bank of India's entry names and enforces the 60,000 rupee daily cap per sender over India's calendar day, compared as exact fractions. Pix pays only a payee with a Pix key on file. The China rail never pays an institution directly and is never proposed, because no mandate allows that corridor. Each simulated rail runs one of five scripts, normal, delayed, held for review, returned, or a scam message inside the status, so the trace and the Protect features can be tested. Every rail honours the idempotency rule in the `Rail.execute` contract: the same key and request return the first receipt, the same key with any difference raises and charges nothing.

## 3. Security design

### 3.1 Instruction provenance

Only the student's own turn can authorise an action. Text arrives with a `Source`: user turn, pasted text, tool result, translated text, provider status or standing mandate. The engine refuses anything not from the user turn under R01. The loop traces each payment detail back to where it first appeared, so a payee or amount the student never typed but a paste or a tool result did makes the action data, and the ledger records `injection_suspected`.

### 3.2 Deterministic authorisation

The engine imports only the Python standard library, the contracts and three helper modules for tiers, formatting and schedules. It makes no model call and no network call. The council and the model only advise or propose; neither can allow or refuse.

### 3.3 Confirmation integrity

Every T2 action needs the token round trip in the same conversation, the token is bound to the exact action, and it is never stored in a reply: the API strips it from decisions, and the reply guard redacts any issued token the model echoes.

### 3.4 Limits and evasion

Per transaction and daily limits are checked against the executed history, so splitting a payment is caught by R09. A new payee waits 24 hours. A standing mandate run outside its pattern escalates to a full confirmation. The UPI to PayNow cap counts across a sender's mandate versions and India's day.

### 3.5 Tamper evidence

The hash chain, the anchor and the integrity hold in 2.5. The ledger is append only: there is no edit or delete operation anywhere in the code.

### 3.6 Secrets and data

Secrets are read only from `.env`, which git ignores. In production the API refuses to start without its two secrets. Outside production, public development secrets are used and labelled as such. The reply guard redacts runs of 13 or more digits, issued tokens, and the values of the four secrets. Conversation memory is kept apart from the ledger and can be erased per student without breaking the chain. Nothing personal reaches the anchor or the chain.

### 3.7 Honest labels

Every route and receipt carries `simulated`. A fee, limit or duration with no source is either a fixture marked as such in the code, or absent, and a trace with no sourced duration says so.
