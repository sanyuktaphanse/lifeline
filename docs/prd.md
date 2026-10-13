# Lifeline product requirements document

Product requirements for Lifeline, the team's entry to the 2026 Shenzhen FinTechathon, International Track, Topic C. Written by Joanne on 13 October 2026 from the rules in `docs/hackathon/rules.md`, the master plan in `docs/hackathon/`, and what `main` holds today. Every status below was checked against the repository on that day; a requirement marked built names where it lives. The technical documentation, `docs/technical_documentation.md`, and the security self assessment, `docs/self_assessment.md`, are the submission documents; this file says what the product is for and what it must do.

## 1. Summary

Lifeline is an AI agent that keeps an international student's money moving and safe across borders. It has two jobs. Move: send rent, allowances and recurring payments over the best legal route, within limits the student set, after a confirmation. Protect: refuse instructions hidden in scam messages, walk the student through a lost card, and check what a provider will ask before the student is flagged. The model proposes, a deterministic engine decides, a rail executes and a hash chained ledger records.

## 2. The problem

### 2.1 What the competition asks

The International Track's theme is "AI as a Financial Participant": an agent that completes real tasks in a financial scenario. Topic C asks for "solutions addressing real financial pain points of international students and cross border users, such as remittances, tuition payments, credit building, and multi currency management."

### 2.2 What students face

1. Moving money is confusing and costly. Every route has its own fee, exchange cost, arrival time, limits and permitted purposes, and every country adds rules, such as India's 60,000 rupee daily cap on UPI to PayNow and China's yearly foreign currency quota.
2. Students far from home are prime targets for scams: a fake bank asking for a transfer to a "safe account", a release fee for a stuck transfer, a request for documents through an outside link.
3. When a card is lost or an account closes, there is no plan B. A bank's app helps only with that bank's card, at the moment the student most needs help.
4. Family is part of it. Parents send money from home and want to know it arrived and that their child is safe.

### 2.3 Why existing tools do not solve it

| | A bank's or provider's agent | A treasury agent for companies | Lifeline |
| --- | --- | --- | --- |
| Serves | One provider's customer, one card | A company moving wires | One student, across every card and route they have |
| When a provider fails | Goes silent | Not its concern | The moment it is built for |
| Safety | The provider's own controls | Sanctions screening | Limits in code, same turn confirmation, a tamper evident record |

## 3. Users

| User | Situation | What they need |
| --- | --- | --- |
| The student abroad, the primary user | Studying in Singapore, paying rent to a landlord in Brazil, with parents in China or India | Pay safely in a few taps, understand every cost, get help fast when a card is lost, never be fooled by a message |
| The parent at home | Sending money to the student from India or China | Know the money arrived, be told truthfully when something went wrong |
| The judges | WeBank industry experts and university scholars | See real tasks completed, security they can verify, and an experience that is new and easy |

The demo runs as one demo student, `student_001` in `fixtures/demo_user.yaml`, and one demo parent, `fixtures/demo_parent.yaml`.

## 4. Goals and non goals

### 4.1 Goals

1. Complete the student's real money tasks end to end: quote, propose, confirm, pay, trace, cancel, remind, summarise.
2. Make every money moving action safe by construction: the model never decides, the engine does, and the student confirms.
3. Be honest everywhere: simulated routes, sample data and features not yet built are labelled as such.
4. Serve the student in their language: English, Portuguese and Chinese.
5. Feel calm and simple on a phone, especially at a stressful moment.

### 4.2 Non goals, the never list

1. Lifeline never holds, pools or settles customer money; licensed partners would.
2. Lifeline never gives investment, yield or tax advice, and never forecasts an exchange rate.
3. A model never decides whether an action is allowed.
4. Lifeline never acts on an instruction that did not come from the student's own turn.
5. Lifeline never states a fee, limit or rule that is not in the knowledge base with a source.
6. Lifeline never hides that a route is simulated, and never puts money on a blockchain; only ledger hashes go there.

## 5. How Lifeline is graded, and what answers each part

The rules, section 3, score every topic the same way.

| Criterion | Weight | What Lifeline offers | Evidence |
| --- | --- | --- | --- |
| Task completion | 40% | The task suite of 38 student tasks: 31 pass automatically, 0 fail, 7 are not automated. The stranger test of 9 October and its fixes: 16 of 17 stranger runs now pass, 1 is expected failing | `make evidence`, `suites/tasks.yaml`, `docs/stranger_test.md` |
| Security and compliance | 30% | Fourteen deterministic rules, four permission tiers, same turn confirmation tokens bound to the exact action, instruction provenance, a hash chained ledger anchored on FISCO BCOS, 27 of 28 attacks blocked automatically | `docs/self_assessment.md`, `suites/attacks.yaml`, 1582 tests |
| Innovation and interaction | 30% | The person's agent positioning, the lost card rescue, the five voice council, three languages, the app in `app/` and the phone first mockup in `mockup/` | `app/`, `mockup/`, the demo video |
| Challenge bonus | 0 to 5 points | The ledger head anchored on FISCO BCOS, WeBank's own chain. Whether it counts for Topic C is not stated; the organisers have been asked | `chain/`, `core/anchor_fisco.py` |

The submission itself, rules section 5, due 20 October 2026 at 23:59 Beijing time, needs: technical documentation, a presentation deck of at most 10 minutes, a demo video of at most 5 minutes, the source code with README, deployment instructions and tests, the security self assessment, and execution evidence from simulated or sandbox operation logs. `docs/hackathon/requirements.md` tracks each.

## 6. Requirements

Priority P0 is needed for the submission on 20 October, P1 is wanted if time allows, and R is roadmap, shown in the deck and the app's Coming next screen as planned, not built.

### 6.1 Move

| # | Requirement | Priority | Status on 13 October |
| --- | --- | --- | --- |
| M1 | Quote every route for a corridor with its fee, exchange cost, arrival and status; return blocked routes with their reason and source, never hide them | P0 | Built, `rails/fake_router.py`; the Wise sandbox quote in `rails/wise_sandbox.py` when a token is set |
| M2 | Propose a transfer and pay it only after a same turn confirmation, on the route the loop or the council chose | P0 | Built, `core/agent.py`, `core/mandate.py` |
| M3 | Enforce the student's limits, payees, corridors, purposes and a 24 hour cooling period for new payees | P0 | Built, rules R04 to R09 and R14 |
| M4 | Trace a transfer that has not arrived, including one a parent sent, with its stage and what to do now | P0 | Built, `POST /trace`, the simulated rails' scripted statuses |
| M5 | Recurring payments confirmed once and run within their pattern, with notice and a cancel window | P0 | Built, rules R12 and R13, `core/standing.py` |
| M6 | Cancel a transfer that has not moved on | P0 | Built, `cancel_transfer` |
| M7 | Reminders and a monthly note of fees, exchange cost and routes, built from the ledger | P1 | Built, `GET /reminders`, `GET /note/{user_id}/monthly` |
| M8 | Corridors Singapore to Brazil over Pix, India to Singapore over UPI to PayNow, China to Singapore, each with sourced rules | P0 | Built and simulated, `rails/sim/` |
| M9 | A real payment through Wise's sandbox, with an operation log as execution evidence | P0 | Built, `make evidence-wise`; needs a sandbox token, not set up yet |
| M10 | Pay tuition the way the university asks | R | Lifeline explains the route, such as NUS asking for Flywire or Convera, but does not pay it |
| M11 | Ask family for money | R | Not built; the student can trace money family sends |
| M12 | Build credit abroad | R | Not built |
| M13 | Real money through licensed partners | R | Not built; every route is simulated, a fixture or a sandbox |

### 6.2 Protect

| # | Requirement | Priority | Status on 13 October |
| --- | --- | --- | --- |
| P1 | Treat pasted text, tool results, translations and provider messages as data; only the student's own words start an action, and the reply says what was blocked | P0 | Built, rule R01, the `blocked` reply field |
| P2 | Recognise a request for documents through an outside channel as suspicious | P0 | Built, the `document_request` precheck |
| P3 | Lost card rescue: identity question, freeze or a deep link, the backup card, emergency money as a confirmed transfer, the family told truthfully | P0 | Built, `core/rescue.py`, states S0 to S9 |
| P4 | Check what a provider will ask before a scrutinised action, such as enabling Pix or remitting from China | P0 | Built, `POST /precheck` |
| P5 | Warn before the student reaches China's overseas cash cap | P1 | Built, the cash cap warning |
| P6 | Explain a foreign message and flag any payment instruction in code | P1 | The translator is built in `rails/translator.py`; the agent does not call it yet, open item 181 |
| P7 | The student sets up their own safety plan before leaving home | R | The plan is a demo fixture today |

### 6.3 Trust and records

| # | Requirement | Priority | Status on 13 October |
| --- | --- | --- | --- |
| T1 | Every proposal, decision, confirmation, execution and receipt is a ledger entry; verify names the first broken entry; a broken ledger pauses payments | P0 | Built, `core/ledger.py`, the integrity hold |
| T2 | Anchor the ledger head outside the app, locally signed or on FISCO BCOS | P0 | Built, `core/anchor_local.py`, `core/anchor_fisco.py` |
| T3 | Show the student their history in plain words, with a verified badge | P0 | Built in the app's ledger view and the mockup's Activity screen |
| T4 | Never show a card number, token or secret in a reply | P0 | Built, the reply guard; known gaps in open items 101, 109 and 110 |

### 6.4 Language

| # | Requirement | Priority | Status on 13 October |
| --- | --- | --- | --- |
| L1 | Replies in English, Portuguese and Chinese, the language detected or chosen | P0 | Built |
| L2 | Every label of the app in the three languages, with a language picker | P0 | Built in `app/` and in `mockup/` |
| L3 | Chinese reviewed by a native speaker | P0 | Done by Joanne on 11 October, pull request 49 |
| L4 | Portuguese reviewed by a native speaker | P1 | Reviewed by SP, not a native speaker; open |

### 6.5 The app and its experience

The mockup in `mockup/` is on the branch `joanne/mockup` and not on `main`; the team decides what of it moves into `app/`.

| # | Requirement | Priority | Status on 13 October |
| --- | --- | --- | --- |
| A1 | Phone first: usable with one thumb on an iPhone screen, large tap targets | P0 | Built in `mockup/`; `app/` is phone first too |
| A2 | Calm and minimal: one main action per screen, the lost card action always one tap away | P0 | The mockup's welcome, Home and tab bar |
| A3 | Suggested prompts for the most common tasks, only ones the backend can do | P0 | Built in the mockup's Chat |
| A4 | A payment sheet that shows amount, payee, purpose, route, fee, exchange cost, arrival, total and the confirmation's expiry before one confirm | P0 | Built in the mockup |
| A5 | Every simulated route, sample reply and unbuilt feature labelled | P0 | Built: Simulated, Sample and Coming soon tags |
| A6 | Sign in | P1 | The API has no sign in, self assessment open item 37. Pull request 55, in review, adds a passphrase lock that would let a simple real lock screen exist; Face ID, Apple and Google stay roadmap |
| A7 | A hosted preview teammates and judges can open on a phone | P1 | The mockup on Netlify, with labelled sample data when no API runs |
| A8 | Install on the home screen like an app | R | Not built |

## 7. Key user journeys

1. Pay rent. The student taps Pay rent, Lifeline proposes 1,200 SGD to the landlord, the payment sheet shows every route and cost, the student confirms within five minutes, and the receipt and ledger entries appear.
2. A scam message. The student attaches a message claiming to be from their bank and asks whether it is a scam. The reply opens with what was blocked and why, nothing moves, and the ledger records the attempt.
3. A lost card. The student taps Lost card, answers the safety question, freezes the card, moves payments to the backup card, takes emergency money to their own account, and the family is told.
4. Money from home. The student asks where their parents' transfer is; Lifeline traces it, says the stage and what to do, and warns against anyone asking for a release fee.

## 8. Non functional requirements

1. Security: every money moving action passes `MandateEngine.check`, which makes no model call; tokens are bound to the exact action and expire after 300 seconds; secrets live only in `.env`.
2. Privacy: the ledger and the chain hold no names or personal data beyond the demo ids; conversation text is erasable per student; the anchor holds only hashes.
3. Honesty: no figure without a source; simulated, sample and roadmap labels everywhere they apply.
4. Accessibility: text at 4.5 to 1 contrast or more, screen reader labels, Reduce motion and Reduce transparency respected, tap targets of 44 points.
5. Reliability in China: the demo runs on a laptop with the fallback model provider, the local anchor or a local FISCO BCOS network, and no dependency on hosts that may be unreachable, `docs/deployment.md`.

## 9. Milestones

| Date | Milestone |
| --- | --- |
| 15 October 2026 | Team build deadline and the demo video recorded |
| 17 October 2026 | Fact freeze proposed: knowledge entries checked and dated |
| 19 October 2026 | Everything submitted, a day early |
| 20 October 2026, 23:59 Beijing time | Official deadline for registration and submission |
| By 31 October 2026 | Finalists announced |
| 20 to 23 November 2026 | Grand Final in Shenzhen |

## 10. Risks and open questions

1. The model's words can be wrong even when the engine holds; the stranger test is the measure, and a second run after the fixes is planned.
2. No real money rail; the Wise sandbox log needs a token that is not set up yet.
3. Knowledge entries' second checks: Brazil, India, Singapore and providers by Pearlin, China by Sanyukta, not needed for the submission but listed as a known limitation.
4. The fixture bank wire and Wise routes say they are not simulated, so the loop prefers them over the sandbox, open item 178.
5. Open questions for the organisers: how the submission is delivered, and whether the FISCO BCOS anchor counts toward the bonus for Topic C.
6. Which of the mockup's designs move into `app/` is the team's decision.
