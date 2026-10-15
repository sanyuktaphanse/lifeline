# Release checklist

This checklist is built from Stage 18 of `docs/build_program.md`, the six submission items of `docs/hackathon/rules.md` section 5, and the submission gate of the master plan, section 6.1: the package checklist ticked by two people independently and opened on a machine none of us owns. The master plan has no release checklist of its own; its appendix C is the rescue state machine.

Each line says what is checked, how it is checked, and the result of the run of 15 October 2026 on branch `lane-a/final-docs`, made on a Mac with Apple silicon in a fresh clone in the system temporary folder, outside the repository, so that no `.env` was read. Every step ran on commit `edf7e67`. The documentation's test counts were then brought up to date, and items 1 to 5 ran again in a second fresh clone at commit `ab18757`, which is the run items 4 and 5 report. Both clones were removed afterwards.

## The clean machine steps of Stage 18

| Item | How it is verified | 15 October 2026 |
| --- | --- | --- |
| 1. A fresh clone holds no `.env` | `git clone` into the system temporary folder, then `ls -a` | Verified: no `.env`, only `.env.example` |
| 2. `python3.12 -m venv .venv`, or `python3.13 -m venv .venv` if that is what you have, as the README says | Run in the clone | Verified with `python3.13 -m venv .venv`, Python 3.13.9, because this machine has no Python 3.12 |
| 3. `pip install -r requirements.txt` | Run in the activated `.venv` | Verified |
| 4. `pytest` | Run in the clone; the count must match the README | Verified at `ab18757`: 1635 passed, 3 skipped, 4 expected failures, 1642 collected, as the README says. At `edf7e67` the same 1642 tests gave 1632 passed and 3 failed, the three tests that check the documents name the collected count, because the documents still said 1632; that is what the count update fixed |
| 5. `make evidence` | Run in the clone; the printed line must match the README | Verified: `58 passed, 0 failed, 8 not automated; stranger runs: 16 passed, 1 expected failing, 0 failed, 0 passes but flagged`, and `evidence/report.md` written |
| 6. `make dev`, then `GET /health`, then stop | Run in the clone, `curl http://127.0.0.1:8000/health` | Verified: port 8000 was free, `make dev` started the API on it, `GET /health` answered `{"status":"ok",...}` with the three languages and `"passphrase_required":false`, and the API was stopped |
| 7. `cd app`, `npm ci` | Run in the clone with Node 22.23.3 | Verified |
| 8. `npm test` | Run in `app/` | Verified: 144 tests, 144 passed |
| 9. `npx playwright test` | Run in `app/` after `npx playwright install chromium` | Verified: 90 tests, 90 passed, `tests/e2e/4-turn-line.spec.js:36` included, which failed in the run of 13 October |
| 10. CI runs both jobs, `python` and `app` | The pull request's checks | Not recorded on this page: the checks of the pull request that adds this run are reported on that pull request. The last run recorded here, on pull request 53, passed both jobs |

## The six submission items

| Item | How it is verified | 15 October 2026 |
| --- | --- | --- |
| 1. Technical documentation | `docs/technical_documentation.md` exists and `tests/test_technical_documentation.py` passes | Verified |
| 2. Presentation deck | `docs/submission/README.md` says where it is | Attached to the submission form, as `docs/submission/README.md` says; it is not in the repository, so this run could not open it |
| 3. Demo video, no more than 5 minutes | `docs/submission/README.md` says where it is | Attached to the submission form, as `docs/submission/README.md` says; it is not in the repository, so this run could not open it or time it |
| 4. Source code with README, repository link, deployment instructions and test cases | `README.md`, `docs/deployment.md`, `tests/` and `app/tests/` exist, and the clean machine steps above run | Verified that they exist; the steps are as above |
| 5. Security self assessment | `docs/self_assessment.md` exists and `tests/test_self_assessment.py` passes | Verified |
| 6. Execution evidence | `make evidence` writes `evidence/report.md`; `suites/scenarios/stranger/`, `docs/stranger_test.md` and `chain/evidence.md` exist; `evidence/wise-sandbox.md` from `make evidence-wise` | The report, the stranger runs and the chain record verified; the Wise sandbox log not verified, because no Wise sandbox run has been made |

## The submission gate

| Item | How it is verified | 15 October 2026 |
| --- | --- | --- |
| 1. The package checklist ticked by two people independently | Two team members each tick this page | Not verified: not ticked by anyone yet |
| 2. Opened on a machine none of us owns | The clean machine steps run on such a machine | Not verified: the run above was on a team member's machine |
