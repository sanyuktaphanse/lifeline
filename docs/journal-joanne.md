# Lane B journal, Joanne

Lane B is rails and knowledge: the router, the rails, the Wise sandbox, the simulated Pix and UPI to PayNow rails, the knowledge base, the translator, the README, the deployment guide and the execution evidence pack. Sanyukta's journal for lane A is `docs/journal.md`.

# 10 October 2026

## What I did

I set up the repository on my laptop with Python 3.12 and ran everything: 1428 tests passed, 3 skipped, 4 expected failures, and the evidence report gave 58 passed, 0 failed and 8 not automated.

I added `docs/hackathon/` with the organisers' rules, the official deadline of 20 October 2026 at 23:59 Beijing time, the team deadline of 15 October, and the submission checklist mapped to the repository.

I built the Wise sandbox rail in `rails/wise_sandbox.py`. It quotes, creates and funds a transfer on Wise's sandbox, traces it through Wise's own statuses, and cancels it. It runs only when a sandbox token is in `.env`, and everything it does is marked simulated, because no real money moves. `make evidence-wise` writes the sandbox operation log the rules ask for. 47 new tests cover it with a fake Wise server, so no test calls the internet.

## What I learned

The rails were already further along than the master plan's calendar said: lane A had built the simulated Pix, UPI to PayNow and China rails and made the knowledge corrections. What was missing was the one real provider.

Wise uses `customerTransactionId` to stop duplicate transfers, which fits our idempotency key exactly: the same key and the same request always give Wise the same id, so a retry cannot pay twice.

The agent prefers routes that are not simulated. Because the fixture bank wire says it is not simulated, the agent picks it over the honest sandbox Wise route on Singapore to Brazil. That is a lane A decision, so it is open item 168.

## What is next

1. Get a Wise sandbox token, profile id and recipients into `.env`, top up the sandbox balance, and run `make evidence-wise`.
2. Put my initials in `second_check_by` for the knowledge entries in `docs/knowledge_audit.md`, after opening each page.
3. The translator, which no one has built yet.
4. The deployment guide.
