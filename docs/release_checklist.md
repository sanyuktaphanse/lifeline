# Release checklist

This checklist is built from Stage 18 of `docs/build_program.md`, the six submission items of `docs/hackathon/rules.md` section 5, and the submission gate of the master plan, section 6.1: the package checklist ticked by two people independently and opened on a machine none of us owns. The master plan has no release checklist of its own; its appendix C is the rescue state machine.

Each line says what is checked, how it is checked, and the result of the run of 13 October 2026 on branch `lane-a/release` at commit `a6e0607`, made on a Mac with Apple silicon in a fresh clone in the system temporary folder, outside the repository, so that no `.env` was read. The clone was removed afterwards.

## The clean machine steps of Stage 18

| Item | How it is verified | 13 October 2026 |
| --- | --- | --- |
| 1. A fresh clone holds no `.env` | `git clone` into the system temporary folder, then `ls -a` | Verified: no `.env`, only `.env.example` |
| 2. `python3.12 -m venv .venv`, or `python3.13 -m venv .venv` if that is what you have, as the README says | Run in the clone | Verified with `python3.13 -m venv .venv`, Python 3.13.9, because this machine has no Python 3.12 |
| 3. `pip install -r requirements.txt` | Run in the activated `.venv` | Verified |
| 4. `pytest` | Run in the clone; the count must match the README | Verified: 1575 passed, 3 skipped, 4 expected failures, 1582 collected, as the README says |
| 5. `make evidence` | Run in the clone; the printed line must match the README | Verified: `58 passed, 0 failed, 8 not automated; stranger runs: 16 passed, 1 expected failing, 0 failed, 0 passes but flagged`, and `evidence/report.md` written |
| 6. `make dev`, then `GET /health`, then stop | Run in the clone, `curl http://127.0.0.1:8000/health` | Not verified as written: `make dev` stopped with `[Errno 48] Address already in use`, because an API started from the main working folder on 11 October holds port 8000. The Makefile's same command on port 8001 answered `{"status":"ok",...}` with the three languages, and was stopped |
| 7. `cd app`, `npm ci` | Run in the clone with Node 22.23.3 | Verified |
| 8. `npm test` | Run in `app/` | Verified: 70 tests, 70 passed |
| 9. `npx playwright test` | Run in `app/` after `npx playwright install chromium` | Not verified: 45 passed, 1 failed. `tests/e2e/4-turn-line.spec.js:36`, DOCUMENTED SHAPE: a blocked paste puts its sentence at the top, the turn line at the bottom, fails with `Expected: "reply-blocked"`, `Received: undefined`. It fails the same way on `main` at `06b3c30` |
| 10. CI runs both jobs, `python` and `app` | The pull request's checks | Verified on pull request 53: `python` passed, and `app` passed with 70 of 70 unit tests and 46 of 46 Playwright tests on Ubuntu, the test of item 9 included |

## The six submission items

| Item | How it is verified | 13 October 2026 |
| --- | --- | --- |
| 1. Technical documentation | `docs/technical_documentation.md` exists and `tests/test_technical_documentation.py` passes | Verified |
| 2. Presentation deck | Its path or link in `docs/submission/README.md` | Not verified: pending, in progress with Joanne |
| 3. Demo video, no more than 5 minutes | Its path or link in `docs/submission/README.md` | Not verified: pending, in progress with Pearlin |
| 4. Source code with README, repository link, deployment instructions and test cases | `README.md`, `docs/deployment.md`, `tests/` and `app/tests/` exist, and the clean machine steps above run | Verified that they exist; the steps are as above |
| 5. Security self assessment | `docs/self_assessment.md` exists and `tests/test_self_assessment.py` passes | Verified |
| 6. Execution evidence | `make evidence` writes `evidence/report.md`; `suites/scenarios/stranger/`, `docs/stranger_test.md` and `chain/evidence.md` exist; `evidence/wise-sandbox.md` from `make evidence-wise` | The report, the stranger runs and the chain record verified; the Wise sandbox log not verified, pending a sandbox token |

## The submission gate

| Item | How it is verified | 13 October 2026 |
| --- | --- | --- |
| 1. The package checklist ticked by two people independently | Two team members each tick this page | Not verified: not ticked by anyone yet |
| 2. Opened on a machine none of us owns | The clean machine steps run on such a machine | Not verified: the run above was on a team member's machine |
