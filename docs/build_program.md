# Lifeline, lane A build program for Claude Code

Version 1, 18 September 2026. Owner: Sanyukta. This file is the complete remaining build for lane A, in the order it must run. Every stage is one pull request. Nothing starts until the previous pull request is merged. Paste the word ultracode at the front of a prompt where the stage says so; if your Claude Code version does not support workflows it runs the same prompt as one agent, which is fine.

Keep this file in the repository at docs/build_program.md so the team can see where lane A is.

## Part 0. Rules that never change

### 0.1 The standing instruction

Paste this once at the start of every Claude Code session, before anything else.

For every task in this session: work on a branch cut from an up to date main, never on main. Read the files you will touch before writing. If anything in my instruction does not match the code, stop and tell me before writing. Write tests before code. Every fact about a limit, fee, rule or rail status must cite a knowledge base entry with a source; never hardcode a number. Never write files outside the repository. Never run git push force, git reset hard, or delete branches. Update docs/technical-reference.md and docs/code-walkthrough.md in the same pull request as the change, and check every code excerpt in the walkthrough still matches the source. When done: run the full test suite, run make evidence, commit, push the branch, open a pull request with the template, wait for CI, and report in plain sentences with no dashes: what you changed, what you decided on your own, what you left open with a numbered open item, and the new test count and evidence numbers.

### 0.2 The merge gate, yours, every time

Before you click Merge on any pull request, all five are true:

1. CI is green and the evidence report artifact was uploaded.
2. You have read the Files changed tab once, top to bottom, even the parts you do not follow.
3. The specific checks listed under that stage below are satisfied.
4. You have typed two sentences in the description yourself: what this change does, and why it matters for a student.
5. Nothing is queued in Claude Code behind this build.

If any of the five is false, do not merge. Tell Claude Code what is missing and wait.

### 0.3 The rhythm

Paste one prompt. Wait for the report. Read the report's "decided on my own" and "left open" sections; those are where your judgement is needed. Review and merge. Pull main. Paste the next prompt. Never two builds at once.

### 0.4 When Claude Code asks a question

If it asks about a base branch, the answer is always: wait until I merge, then cut from main. If it proposes a design where the loop refuses something on its own, the answer is: the loop proposes, the engine decides; route it through the engine. If it proposes storing a token anywhere, the answer is no. If it proposes a number for a limit, fee or duration, the answer is: knowledge base entry with a source, or leave it as a fake clearly labelled.

## Part 1. Finish the core (tonight and tomorrow)

### Stage 1. Conversation memory in its own store

Purpose: the ledger is the money trail and is tamper evident; a student's words are personal data with a right to erasure. They must not share a hash chain.

Prompt:

Switch to main, pull, create branch lane-a/memory-store. Move conversation memory out of the ledger into data/conversations.jsonl, append only, per user, erasable per user with a function erase_conversation(user_id) that leaves the ledger untouched. The ledger keeps a turn entry with the count of messages and no text. /ledger no longer returns the student's words. Rebuild memory on startup from the conversation store. Keep every existing behaviour and test for memory and provenance passing. Close open item 42. Add to CLAUDE.md: never write files outside the repository folder. Update both docs, commit "Conversation memory in its own erasable store; ledger holds money events only", push, open a pull request, wait for CI, report.

Your checks before merge: core/ledger.py stores no message text; erase_conversation exists and has a test; the provenance tests still pass; /ledger response in docs/api.md no longer shows student words.

### Stage 2. Standing mandates, rules R12 and R13

Purpose: automation under a mandate the user set, never an invented payment. This is the answer to "can it automate international payments."

Prompt:

Switch to main, pull, create branch lane-a/standing-mandates. Read contracts/schemas.py for the existing StandingMandate model and use it. One: add ActionType create_standing_mandate at tier T2 with warning key warn.standing.new, and cancel_standing_run at tier T1. Two: engine rule R12: an action carrying a standing_mandate_id that matches an active, confirmed standing mandate on the user's current mandate version, with the same payee, corridor and purpose, an amount within tolerance_pct of the standing amount, a requested_at inside the schedule window, and no run already executed for that period, is allowed at tier T1 with rule R12 and no confirmation. Three: engine rule R13: an action carrying a standing_mandate_id where anything is outside that pattern is treated as an ordinary T2 transfer needing confirmation, with R13 in the rule ids and the reason naming what fell outside. Four: in the loop, a tool create_standing_mandate goes through the T2 confirmation round trip and, on confirmation, adds the standing mandate to a new mandate version; a method run_due_standing_mandates(now) finds active standing mandates due within notice_hours, writes a pre notice as a ledger note and returns it for the app, and once the cancel window has passed without a cancel_standing_run, executes the run through the router and rail under R12, writing proposal, decision, execution and receipt against the standing mandate id; cancel_standing_run records the cancellation and skips that period. Tests for every clause of R12 and R13, the creation round trip, a run that executes, a run that is cancelled, and an out of pattern amount escalating to T2. Add scenario T34. Update both docs and the decisions log, commit "Standing mandates: R12 runs within pattern as T1, R13 escalates outside it", push, open a pull request, wait for CI, report.

Your checks before merge: R12 requires all of active, confirmed, current version, same payee corridor purpose, amount within tolerance, inside window, no run this period; R13 escalates anything outside to T2; each clause has its own test; the run writes proposal, decision, execution, receipt against the standing mandate id; the pre notice is a ledger note.

### Stage 3. Evidence gaps (ultracode)

Purpose: the harness is what the 40 percent is scored against. Every entry the code can already satisfy must have a scenario, and no scenario may be hollow.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/evidence-gaps. For every entry in suites/tasks.yaml and suites/attacks.yaml that the harness reports as not automated and that the current code can already satisfy, write a scenario file in suites/scenarios, one agent per scenario. Then a second, independent agent verifies each new scenario actually exercises what its suite entry means, checks the ledger kinds in order, and rejects any scenario that would pass on an empty reply. Do not change core code. If a scenario needs a small fixture, add it under fixtures/. Report the new pass count and list every entry that still cannot be automated with the exact missing capability. Update both docs, commit "Evidence: scenarios for every entry the code can satisfy", push, open a pull request, wait for CI, report.

Your checks before merge: open two new scenario files at random and compare them with their suite entry; the evidence report pass count rose; no file under core/ changed.

### Stage 4. The council

Purpose: the decision method that makes the agent a financial participant. Advisory only; the engine still decides.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/council. Build core/council.py implementing the Council interface. Five voices, cost, speed, safety, rules and timing, each a separate adapter call with its own short system prompt, each returning a position (a route or a wait), a confidence between 0 and 1, and the evidence ids it used from the routes and the knowledge base. A chair reconciles them and returns the chosen route, the runner up, a plain reason, and a disagreement score equal to one minus the share of voices agreeing with the chair. The loop convenes the council only when the escalation rule fires: amount above half the per transaction limit, first transfer on a corridor, first transfer to a payee, cheapest and fastest routes differ and no urgency was stated, any candidate rail degraded or down, or the user in a rescue state. When the disagreement score is above 0.4 the reply presents the runner up as well. The council's output is advisory; the chosen action still goes through the engine. The full transcript is a ledger entry of kind council with no token in it. The fast brain and the council may use different models set by ANTHROPIC_MODEL and ANTHROPIC_COUNCIL_MODEL, with the same for the fallback provider; add them to .env.example. Tests with the fake adapter for each escalation trigger, for the disagreement score, for the runner up being shown, and for the council never executing anything. Scenario T21. Update both docs and the decisions log, commit "Council: five voices and a chair, advisory, escalation rule", push, open a pull request, wait for CI, report.

Your checks before merge: the council has no way to call a rail or the engine's execute path; every escalation trigger has a test; the transcript entry contains no token; the model names come from environment variables.

### Stage 5. The anchor, local and FISCO BCOS

Purpose: tamper evidence for the ledger head, anchored outside our own control. Swappable; the product works identically without the chain.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/anchor. contracts/interfaces.py already declares Anchor. One: implement core/anchor_local.py LocalSignedAnchor that writes the ledger head hash, sequence, a hashed user id and a timestamp to data/anchors.jsonl with an HMAC signature from LIFELINE_ANCHOR_SECRET, and verify(head_hash) that returns the anchored time or None and detects a tampered line. Two: implement chain/LifelineEvidence.sol with anchor(bytes32 head, uint64 seq, bytes32 userHash) storing head, seq, block timestamp and sender and emitting an event, and verify(bytes32 head) returning the record or zeros. Three: implement core/anchor_fisco.py FiscoBcosAnchor behind the same interface, with a docker compose file under chain/ that starts a four node local FISCO BCOS network using the project's official build chain tooling, and a client that tries the Python route first and JSON RPC second; if neither can be made to work inside this task, leave FiscoBcosAnchor raising a clear NotConfigured error with a message naming what was tried, and write chain/README.md with the exact steps attempted and where they stopped. Four: the loop anchors on every T2 execution and at least once per hour of activity; the anchor reference is itself a ledger entry of kind anchor. Five: /ledger/{user_id}/verify returns both the first broken seq and the head's anchor status with time and, for the chain, block number. Configuration ANCHOR=local or fisco in .env with local the default. Tests for the local anchor including tamper detection; an integration test for the chain anchor skipped unless the network is reachable. Update both docs and the decisions log, commit "Anchor: local signed anchor, FISCO BCOS anchor behind the same interface", push, open a pull request, wait for CI, report.

Your checks before merge: with ANCHOR=local everything passes with no docker; the verify endpoint shows anchor status; the chain README says truthfully whether anchoring worked; no funds, balances or names go to the chain, only hashes and a sequence.

### Stage 6. The rescue state machine

Purpose: the lost card flow is the demo's centre. Appendix C of the master document is the specification.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/rescue. Implement docs Appendix C (the rescue state machine S0 to S9) as core/rescue.py driven through the agent loop and exposed by the API as POST /rescue/start and POST /rescue/step. Each step is an action with its tier through the engine and a ledger entry: S0 detect with the trigger source; S1 identity check as T1; S2 freeze as T2 through the rail, or the honest not_supported path with the deep link; S3 wallet token check as T0 reading the plan; S4 reroute to the backup as T1 when the plan pre authorised it; S5 money in hand, a top up within the standing emergency allowance as an R12 run, beyond it a T2 with confirmation; S6 no backup path with cash pickup options from the knowledge base and a message template to the trusted contact, never a transfer to a new payee; S7 replacement via deep link with an honest delivery estimate from the knowledge base; S8 plan rewrite that reroutes upcoming payments and pauses standing mandates on the frozen instrument; S9 family notice if opted in, truthful including any blocks, and a summary in the user's language. The plan comes from fixtures/demo_user.yaml, extended with backup_instrument, backup_route, wallet_token_present, trusted_contact, cash_plan, emergency_allowance and family_notice_opt_in. Tests for a full rescue with a supporting partner, a full rescue with a not_supported partner, a rescue with no backup, a stranger claiming the card is lost being stopped at S1, and a pasted message during the rescue asking for money elsewhere being refused under R01. Scenarios T14, T15, T16. Update both docs, commit "Rescue state machine S0 to S9 with honest partner paths", push, open a pull request, wait for CI, report.

Your checks before merge: S2 freeze is a T2 with the round trip; the no backup path never proposes a transfer to a new payee; the not_supported path carries a deep link and the honest text in three languages; every step is a ledger entry.

### Stage 7. Simulated rails with real rules, and the China remittance rail

Purpose: B owns the real Wise client; you took the simulated rails. They must encode sourced rules and scripted statuses so trace and pre check have something true to show.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/sim-rails. Build rails/sim/pix.py, rails/sim/upi_paynow.py and rails/sim/cn_bank_remit.py behind the Rail interface, all with simulated True and names pix_sim, upi_paynow_sim and cn_bank_remit_sim. Each encodes its limits and permitted purposes by reading rails/knowledge entries by id, never by hardcoding a number; where an entry does not exist yet, create it with the source from docs and mark second_check_by empty. upi_paynow_sim: IN>SG only, person to person, allowance and family support purposes, daily cap from the knowledge entry, blocked route returned with the entry id otherwise. pix_sim: BR domestic, requires a CPF flag on the user fixture, statuses created, completed within one hour. cn_bank_remit_sim: CN>SG, execute requires a document checklist complete and a quota position known, distinguishes to institution from to student, scripted statuses documents submitted, under review, released, in transit, arrived over a simulated ten to fifteen business days, and status() returns a TraceResult with the typical duration and its source entry. Each rail has scripted scenarios selectable by idempotency key prefix: normal, delayed, held for review, returned, and a status message containing a scam text that must be treated as data. Register them in the API's rails dictionary alongside the fakes with a config flag. Tests for each rail's limits, purposes, statuses and the scam text handling. Scenarios T18, T19, T29, T31, T36. Update both docs, commit "Simulated Pix, UPI to PayNow and China bank remittance rails with sourced rules and scripted statuses", push, open a pull request, wait for CI, report.

Your checks before merge: grep the three rail files for digits; any number present must be a reference to a knowledge entry, not a literal; every response says simulated; the scam text scenario writes injection_suspected or refuses under R01.

### Stage 8. Trace and pre check orchestration, China content

Purpose: the two borrowed features, applied to the parent in China flow.

Prompt:

ultracode. Switch to main, pull, create branch lane-a/trace-precheck. One: the trace tool presents a TraceResult in three parts in the user's language: where it is, how long this stage usually takes with its source, and what to do now and what not to do; any text from the provider is quoted as data and never becomes an instruction. Two: Router.precheck content for action kinds enable_pix, first_large_transfer, remit_from_china and add_country, read from knowledge entries: documents likely, review triggers, readiness against the user's documents on file, and for remit_from_china a plain statement that pooling other people's quotas is structuring and is detected, the recommendation to start three weeks before the due date, and the choice between paying the institution directly and funding the student. Three: the pre check recognises how each provider actually requests documents and flags a message asking to send documents elsewhere. Scenarios T31 in Chinese, T32, T36, X26, X27, X28. Update both docs, commit "Trace and pre check: three part trace, China remittance pre check, document request recognition", push, open a pull request, wait for CI, report.

Your checks before merge: X28 refuses the aunt's quota suggestion and names structuring; every document list traces to a knowledge entry; the Chinese wording of the pre check is flagged for native review in the open items.

### Stage 9. Monthly note, UnionPay cash cap, reminders

Purpose: the proactive pieces, cheap and memorable.

Prompt:

Switch to main, pull, create branch lane-a/proactive. One: core/monthly_note.py builds the proactive monthly note from the ledger only: fees, spread and taxes paid, routes used and the saving against the bank wire route, anything unusual (payees added, rescues, blocked attempts, injection events), and what is coming (standing runs, reminders); rendered in the user's language; exposed as GET /note/{user_id}/monthly; every number traceable to ledger entries listed in the response. Two: track cumulative overseas cash withdrawals on the user's Chinese cards from ledger entries of kind cash_withdrawal against the cap in knowledge entry cn_atm_cap_005, warn at 70 and 90 percent, and explain the two year consequence; a tool record_cash_withdrawal at T1 for the demo. Three: reminders due are returned by GET /reminders/{user_id} so the app can deliver them. Scenarios T13, T35, T37. Update both docs, commit "Monthly note from the ledger, UnionPay cash cap tracking, reminders endpoint", push, open a pull request, wait for CI, report.

Your checks before merge: the note contains no number that is not backed by a listed ledger entry; the cap comes from the knowledge entry; the warning text exists in Chinese.

## Part 2. Hardening (week four, 5 to 11 October)

### Stage 10. Adversarial security review (ultracode)

Prompt:

ultracode. Switch to main, pull. Run an adversarial security review of core/mandate.py, core/agent.py, core/rescue.py and api/main.py against suites/attacks.yaml. One independent attacker per attack class, each trying through the API and the loop with the fake adapter scripted as a compromised model to move money, add a payee, freeze the wrong card, replay a token, stretch a standing mandate, or extract a secret or a token. Three independent skeptics per claimed break who try to refute it. Return only confirmed breaks, each with a failing test that reproduces it. For each confirmed break open a separate pull request on its own branch named lane-a/fix-<attack id> containing the fix and the test, update both docs, wait for CI, and report. Report separately the attacks that were attempted and failed to break anything, so the self assessment can cite them.

Your checks before merge, per fix: the failing test is present and now passes; the fix is in the engine or the schema where possible, not only in the loop.

### Stage 11. Provider swap test

Prompt:

Switch to main, pull, create branch lane-a/provider-swap. Add make evidence-fallback that runs the harness with FALLBACK_MODEL_PROVIDER as the primary against recorded fixtures, and a CI job that runs it weekly and on demand. Add scenarios in Portuguese and Hindi to the swap run. Report the pass rate difference between providers in the evidence report. Update both docs, commit "Provider swap evidence run", push, open a pull request, wait for CI, report.

### Stage 12. Knowledge base audit (ultracode, lane B owns the fixes)

Prompt:

ultracode. On main, do not create a branch. For every entry in rails/knowledge, two independent agents open the source URL and check the statement, the number, the date and the scope. Produce docs/knowledge_audit.md listing agreement, disagreement with the exact difference, unreachable sources, and entries older than 30 days. Change nothing else. Report the counts.

Then send docs/knowledge_audit.md to B; B fixes and second initials the entries in a lane B pull request.

### Stage 13. Multilingual review (ultracode)

Prompt:

ultracode. Switch to main, pull, create branch lane-a/i18n-review. For every user facing string in rails/i18n and every reply template in core, one agent per language checks that the Portuguese and Chinese say what the English says, with money and safety wording exact, that amounts and dates are formatted by locale from one function, and that right to left layout flags exist for the app. Fix only differences the reviewer is confident about; list the rest in docs/i18n_review.md for a native speaker. Update both docs, commit "Multilingual review fixes", push, open a pull request, wait for CI, report.

### Stage 14. Stranger test (ultracode, weekly from now)

Prompt:

ultracode. On main. Act as a judge who has never seen this system. Through the API only, with the fake adapter replaced by the real model, try twenty tasks a student would actually ask in English, Portuguese and Chinese, including typos, mixed languages and one pasted scam message, and report each as worked, worked badly or failed, with the exact request and reply. Add every failure as a scenario file marked expected failing so the evidence report stays honest. Open a pull request with only the scenario files, wait for CI, report.

## Part 3. Documentation and submission (weeks six and seven)

### Stage 15. Documentation truth check (ultracode)

Prompt:

ultracode. Switch to main, pull, create branch lane-a/docs-truth. Compare docs/technical-reference.md, docs/code-walkthrough.md, docs/api.md, README.md and CLAUDE.md against the code on main. One agent per document, then a critic asking what is missing, what is stale, and what is claimed without a test. Fix the docs; touch no code. Update the test counts and evidence numbers from the real run. Commit "Documentation truth check", push, open a pull request, wait for CI, report.

### Stage 16. Security and compliance self assessment

Prompt:

Switch to main, pull, create branch lane-a/self-assessment. Write docs/self_assessment.md following the outline in the master document section 17: permission tiering, deterministic authorisation, instruction provenance, confirmation integrity, limit evasion, payee integrity, tamper evidence, secrets, data and privacy, facts and honesty, what we do not do, known limitations. Every claim cites a rule id, a file and a test name, and the attack suite results come from the latest evidence report by reading the file, not by typing. Include the list of attempted attacks that failed to break anything from the security review. Plain sentences, no dashes. Commit "Security and compliance self assessment", push, open a pull request, wait for CI, report.

Your checks before merge: pick three claims at random and open the test they cite.

### Stage 17. Technical documentation for submission

Prompt:

Switch to main, pull, create branch lane-a/technical-documentation. Produce docs/technical_documentation.md as the submission document: architecture, contracts, tiers and rules R01 to R14, agent loop and council, rails layer and rails map with sourced statuses, ledger and anchor, multilingual design, Protect and the rescue state machine, standing mandates and the monthly note, evaluation method and measured results with the commit hash and the evidence report embedded, deployment including the China fallback, known limitations. Every number from the evidence report; every architectural claim points to a file and a test. Plain sentences, no dashes, no decorative symbols. Commit "Technical documentation for submission", push, open a pull request, wait for CI, report.

### Stage 18. Clean machine and package

Prompt:

Switch to main, pull. Produce a release checklist in docs/release_checklist.md matching the master document Appendix C, then verify each item by running it: fresh clone into a temporary folder inside the repository's tmp/ directory, follow README exactly, run the tests, run make evidence, start the API, call /health, stop. Report each item as verified or not with the exact failure. Tag the commit v1.0-submission only when every item is verified. Do not push the tag until I say so.

## Part 4. Learning prompts, for you, any evening

Tell me the story of one rent payment through this codebase, file by file, in plain English, stopping after each file until I say continue. Then the same for a lost card. Then for a rejected injection.

Explain rules R01 to R14 as a table with one row each: what it checks, an example that passes, an example that fails, and the test that proves it. Then quiz me on five of them and correct my answers.

Pick the three functions in this repository a judge is most likely to ask about, explain each line by line, then tell me the question a skeptical judge would ask about each and the honest answer.

Explain why the loop proposes and the engine decides, with the two places in the code where that boundary lives, and what would go wrong if the loop could refuse or allow on its own.

## Part 5. The cut list, unchanged

If on 15 October demo three misses tasks at 80 percent and attacks at 90 percent, cut in this order: monthly note, T33, FISCO BCOS anchor (local anchor stays), council view in the app, third corridor depth, standing mandates, family notice, live sandbox in the video. Never cut: engine and tiers, ledger with verify, T2 confirmation, Protect onboarding, rescue, trace, pre check, three languages, suites with automated report, README on a clean machine, video under five minutes, technical documentation, self assessment.
