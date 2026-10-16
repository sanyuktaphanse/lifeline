# Release checklist

This checklist is built from Stage 18 of `docs/build_program.md`, the six submission items of `docs/hackathon/rules.md` section 5, and the submission gate of the master plan, section 6.1: the package checklist ticked by two people independently and opened on a machine none of us owns. The master plan has no release checklist of its own; its appendix C is the rescue state machine.

Each line says what is checked, how it is checked, and the result of the run of 16 October 2026 on branch `lane-a/wise-sandbox-log`, made on a Mac with Apple silicon in a fresh clone of that branch from GitHub at commit `e440253`. The clone was made in `.harness_tmp/release-clone/`, a folder inside the repository that git ignores. It held no `.env`, and Lifeline reads `.env` only from the root of the copy the code runs from, so no `.env` was read. The clone was removed afterwards.

## The clean machine steps of Stage 18

| Item | How it is verified | 16 October 2026 |
| --- | --- | --- |
| 1. A fresh clone holds no `.env` | `git clone` into a temporary folder that git ignores, then `ls -a` | Verified: no `.env`, only `.env.example` |
| 2. `python3.12 -m venv .venv`, or `python3.13 -m venv .venv` if that is what you have, as the README says | Run in the clone | Verified with `python3.13 -m venv .venv`, Python 3.13.9, because this machine has no Python 3.12 |
| 3. `pip install -r requirements.txt` | Run in the activated `.venv` | Verified, and `pip check` found no broken requirements |
| 4. `pytest` | Run in the clone; the count must match the README | Verified: 1641 passed, 3 skipped, 4 expected failures, 1648 collected, as the README says |
| 5. `make evidence` | Run in the clone; the printed line must match the README | Verified: `58 passed, 0 failed, 8 not automated; stranger runs: 16 passed, 1 expected failing, 0 failed, 0 passes but flagged`, and `evidence/report.md` written |
| 6. `make dev`, then `GET /health`, then stop | Run in the clone, `curl http://127.0.0.1:8000/health` | Verified: port 8000 was free, `make dev` started the API on it, `GET /health` answered `{"status":"ok",...}` with the three languages and `"passphrase_required":false`, and the API was stopped |
| 7. `cd app`, `npm ci` | Run in the clone with Node 22, as `app/README.md` says | Verified with Node 22.23.3. The machine's default Node was 20.20.2, under which `npm ci` worked but `npm test` found no test files, because Node 20 does not expand the pattern `tests/unit/*.test.js`; both steps were then run again with Node 22.23.3 |
| 8. `npm test` | Run in `app/` | Verified: 144 tests, 144 passed |
| 9. `npx playwright test` | Run in `app/` after `npx playwright install chromium` | Verified: 90 tests, 90 passed |
| 10. CI runs both jobs, `python` and `app` | The pull request's checks | Not recorded on this page: the checks of the pull request that adds this run, pull request 66, are reported on that pull request. Its first push, commit `e440253`, passed both jobs |

## The six submission items

| Item | How it is verified | 16 October 2026 |
| --- | --- | --- |
| 1. Technical documentation | `docs/technical_documentation.md` exists and `tests/test_technical_documentation.py` passes | Verified |
| 2. Presentation deck | `docs/submission/README.md` says where it is | Attached to the submission form, as `docs/submission/README.md` says; it is not in the repository, so this run could not open it |
| 3. Demo video, no more than 5 minutes | `docs/submission/README.md` says where it is | Attached to the submission form, as `docs/submission/README.md` says; it is not in the repository, so this run could not open it or time it |
| 4. Source code with README, repository link, deployment instructions and test cases | `README.md`, `docs/deployment.md`, `tests/` and `app/tests/` exist, and the clean machine steps above run | Verified that they exist; the steps are as above |
| 5. Security self assessment | `docs/self_assessment.md` exists and `tests/test_self_assessment.py` passes | Verified |
| 6. Execution evidence | `make evidence` writes `evidence/report.md`; `suites/scenarios/stranger/`, `docs/stranger_test.md` and `chain/evidence.md` exist; `docs/wise_sandbox_log.md`, the log `make evidence-wise` wrote | The report, the stranger runs and the chain record verified. The Wise sandbox log exists: it was generated on 16 October 2026 on a team member's machine, because `make evidence-wise` reads the sandbox token from `.env`, and was not run again in the clone. It records live quotes and transfers created in Wise's sandbox, and Wise refusing to fund them, so no sandbox transfer completed |

## The submission gate

| Item | How it is verified | 16 October 2026 |
| --- | --- | --- |
| 1. The package checklist ticked by two people independently | Two team members each tick this page | Not verified: not ticked by anyone yet |
| 2. Opened on a machine none of us owns | The clean machine steps run on such a machine | Not verified: the run above was on a team member's machine |
