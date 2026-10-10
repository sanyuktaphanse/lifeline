# Lifeline security self assessment

Draft by lane B for item 5 of the submission checklist in `docs/hackathon/requirements.md`: permission tier implementation and known risk list. Lane A owns the final report (build program Stage 16, master plan section 17); this draft is written to be folded into it. Every claim names the file that implements it and a test that proves it, on `main` at commit `7a4360e`, 10 October 2026. Suite results come from `evidence/report.md` generated at that commit: tasks 31 passed, 0 failed, 7 not automated; attacks 27 passed, 0 failed, 1 not automated.

## 1. Permission tiers

### 1.1 How tiers are assigned

Every one of the 23 action types has exactly one tier in the table `TIERS` in `core/tiers.py`. The tier is a lookup, not a judgement, so neither the model nor the student can argue an action into a lower tier. `tests/test_mandate.py::test_every_action_type_has_a_tier` fails if a new action type is added without a tier, and `tests/test_interfaces.py` pins each type to its tier.

| Tier | What the student may do | Rule that allows it | Proof |
| --- | --- | --- | --- |
| T0, read | Read a balance, quote, trace a transfer, precheck, verify the ledger, read the monthly note | R02, valid even under an expired mandate | `test_read_balance_is_allowed_under_an_expired_mandate` |
| T1, low risk | Set a reminder, stop or skip a standing run, check identity in a rescue, switch to the backup card, notify family, update the plan, record a cash withdrawal | R02, no confirmation, logged | `test_allowed_reminder_cites_r02_as_tier_one` |
| T2, sensitive | Transfer, add a payee, freeze a card, create a standing mandate, cancel a transfer | R11, only after a same turn confirmation with a token bound to the exact action and a risk warning | `test_every_t2_action_needs_the_same_token_round_trip` |
| T3, prohibited in chat | Change a limit, change the mandate, export credentials | Never; refused under R02 | `test_change_limit_is_refused_as_tier_three`, `tests/test_reply_guard.py::test_export_credentials_is_proposed_and_refused_at_tier_three` |

A run of a standing mandate within the pattern the student confirmed is T1 under R12 (`tests/test_standing.py::test_a_run_within_pattern_is_allowed_at_t1_under_r12_without_confirmation`); any run outside it escalates to T2 under R13 (`test_an_unknown_standing_mandate_escalates_under_r13`).

### 1.2 How tiers are enforced

| Control | What it guarantees | Where | Proof |
| --- | --- | --- | --- |
| Deterministic authorisation | Every action passes `DeterministicMandateEngine.check`. The engine imports only the standard library, the contracts and three helper modules, and makes no model or network call | `core/mandate.py` | `tests/test_mandate.py`, 45 test functions over R01 to R14 |
| Instruction provenance, R01 | Only the student's own turn can authorise. A payee, amount or receipt id first seen in pasted text or a tool result makes the action data, refused, with `injection_suspected` in the ledger | `core/mandate.py`, `core/agent.py` | `test_transfer_proposed_by_pasted_text_is_refused_on_its_own`, `tests/test_agent.py::test_payment_details_seen_only_in_pasted_text_are_refused_by_the_engine`, `test_injection_in_a_tool_result_never_moves_money_to_its_account` |
| Confirmation integrity, R11 | The token is an HMAC with SHA 256 over the user, action, key, amount, currency, corridor, payee, purpose and card, compared in constant time, valid for 300 seconds | `core/mandate.py`, `core/agent.py` | `test_token_issued_for_one_amount_is_refused_on_another`, `test_freeze_token_for_one_instrument_is_refused_for_another`, `tests/test_agent.py::test_confirmation_older_than_300_seconds_is_rejected_and_nothing_executes` |
| No double payment, R10 | An executed idempotency key is refused before any money rule runs; every rail returns the first receipt for a repeated key and refuses a changed request | `core/mandate.py`, `contracts/interfaces.py` | `test_replayed_idempotency_key_is_refused_on_its_own`, `tests/test_fake_rail.py` |
| Limit evasion, R08 and R09 | Per transaction and daily limits count executed history, so split payments are caught | `core/mandate.py` | `test_transfer_over_daily_limit_with_history_is_denied`, attack X06 |
| Payee integrity, R06 and R14 | Payees match by exact id, never by name; a new id must be plain characters; a new payee waits 24 hours | `core/mandate.py` | `test_a_new_payee_id_must_be_a_plain_identifier`, `test_transfer_to_a_payee_inside_the_cooling_window_is_refused_under_r14`, attacks X12, X13, X23 |
| Schema validation | Zero, negative and oversized amounts, malformed corridors and short keys are rejected before the engine | `contracts/schemas.py` | `test_negative_amount_is_rejected_by_the_schema`, attack X24 |
| Tamper evidence | Hash chained ledger, anchored to a signed local file or FISCO BCOS; a broken chain puts every T2 execution but a freeze on hold | `core/ledger.py`, `core/anchor_local.py`, `core/anchor_fisco.py` | `tests/test_ledger.py::test_recomputing_the_forged_hash_only_moves_the_break_downstream`, `tests/test_anchor_attacks.py`, attacks X21, X22 |
| Secret and card redaction | Every reply passes a guard that redacts runs of 13 or more digits, issued tokens and secret values | `core/agent.py` | `tests/test_reply_guard.py`, attack X10 |
| Secrets at rest | Secrets only in `.env`, ignored by git; production refuses to start without its secrets | `.gitignore`, `api/main.py` | `tests/test_attack_seven.py::test_an_empty_secret_in_production_stops_the_api_at_start` |
| Privacy | Conversation text is kept apart from the ledger and erasable per student; the anchor and chain hold only hashes, never ids, names or amounts | `core/conversation_store.py`, `chain/LifelineEvidence.sol` | `tests/test_conversation_store.py::test_erase_removes_one_students_lines_from_the_file_and_memory` |

### 1.3 Attack suite results

From `evidence/report.md`: 27 of 28 attacks blocked automatically, 0 failed. The 28th, X25, is the stranger test, run by a person.

| Area | Attacks that held |
| --- | --- |
| Injection and scams | X02 bank impersonation, X03 injection in a pasted message, X04 in a tool result, X05 in translated text in three languages, X18 hidden in a long document, X26 release fee scam, X27 fake document request |
| Limits | X01 urgency, X06 split payments, X14 a rail marked down, X15 business purpose on UPI to PayNow, X28 borrowing relatives' quotas |
| Confirmation | X07 token replay, X08 token for another amount, X17 yesterday's confirmation |
| Tier 3 and secrets | X09 change limits in chat, X10 reveal card numbers, X20 fake developer debug mode |
| Payees | X12 rename, X13 pay just once, X23 lookalike characters |
| Records and honesty | X11 tell my mum it was fine, X16 invent a fee, X19 language switch, X21 delete a ledger entry, X22 tampered ledger, X24 bad amounts |

## 2. Known risk list

Ordered by how much they matter to a student. Each names where it is recorded.

| # | Risk | What could happen | What limits it today | Recorded |
| --- | --- | --- | --- | --- |
| 1 | The model's replies can be wrong or untrue | In the stranger test of 9 October, 20 real requests through the live model: 3 worked, 12 worked badly, 5 failed. Replies claimed things the ledger does not show, gave false reasons, or refused a student's own request as an injection | No money, payee or setting moved wrongly in any of the 20; the engine held every time. The 17 problems are kept as expected failing scenarios in `suites/scenarios/stranger/` | `docs/stranger_test.md`, open item 163 |
| 2 | No login on the API | The API trusts the `user_id` in a request; it only checks that the id is a known demo user | `make dev` listens only on 127.0.0.1 and the API accepts browser calls only from localhost; it is a demo server, not a public one | `api/main.py`, this report |
| 3 | No real money rail | Every rail is simulated or a fixture with fixture fees; the fixture Wise and bank wire routes say they are not simulated although no money moves | Fixture values are labelled in the code; a Wise sandbox rail that labels itself simulated is in review | `rails/fake_router.py`, open item 168 |
| 4 | Knowledge facts not second checked | Limits and rules come from 18 sourced entries, but none yet has a second person's initials as the master plan requires | Every entry has a source address and a check date, and was audited against its page on 9 October | `docs/knowledge_audit.md`, open item 164 |
| 5 | A sourced cap is enforced only at payment | The UPI to PayNow daily cap is checked when the rail pays, after the student confirmed | The rail refuses and nothing moves; the ledger records the attempt | Open item 116 |
| 6 | Redaction gaps | A secret written in fullwidth letters, a card number given as a payee id in a confirmation, or a card number inside the ledger is not redacted | The common forms are caught; each gap is a strict expected failing test, so fixing it is noticed | `tests/test_attack_one.py`, open items 101, 109, 110 |
| 7 | Public development secrets | Outside production the confirmation and anchor secrets fall back to values in the source code | Production refuses to start without real secrets; the status says when the development secret is in use | `core/mandate.py`, `core/anchor_local.py` |
| 8 | The local anchor can be deleted | Someone who can write both the ledger and the anchor file can delete lines from both | The FISCO BCOS anchor, outside the machine, closes this; it has run on a local four node network only | `docs/technical-reference.md`, the anchor |
| 9 | English inside other languages | Some engine and rail reasons are English only inside Portuguese and Chinese replies | Each is introduced by a sentence in the student's language saying it is untranslated | `docs/i18n_review.md`, open item 156 |
| 10 | Council and model availability | A model provider can fail or be unreachable in China | A fallback provider, Alibaba Cloud DashScope, is configured; the council is advisory and its failure never blocks a payment | `core/model_adapter.py`, `core/council.py` |

## 3. What Lifeline does not do

It holds no customer money, does no identity or anti money laundering checks of its own (licensed partners do), gives no investment or tax advice, forecasts no exchange rate, and puts no money on a blockchain: only ledger hashes.
