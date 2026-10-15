# Lifeline

Lifeline is a cross border finance agent for students studying abroad, built for the 2026 Shenzhen FinTechathon. It has two jobs. It helps the student move money across borders, and it protects the student from scams, fraud, and costly mistakes. Every action that moves money passes a plain Python mandate engine first. Lifeline is instructed never to give investment advice; one sentence of the system prompt carries that rule, and no code checks the model's words, as open item 170 of the technical reference records.

This README describes `main` at commit `06b3c30`, 13 October 2026, with the release pull request that adds `docs/submission/README.md`. The repository is https://github.com/sanyuktaphanse/lifeline, which is public since 15 October 2026, so anyone can clone it. Lifeline is released under the MIT licence in [LICENSE](LICENSE), and [docs/licences.md](docs/licences.md) lists the licence of every package in `requirements.txt` and `app/package.json` and of what `chain/setup.sh` downloads.

## Quick start

Lifeline needs Python 3.12 or later. The first command is `python3.12 -m venv .venv`, or `python3.13 -m venv .venv` if that is what you have. [docs/deployment.md](docs/deployment.md) covers a clean machine, every setting in `.env`, the Wise sandbox, the FISCO BCOS anchor and running in China.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
make evidence
make dev
```

Python 3.12 or later is required: `core/agent.py` uses the generic function syntax of 3.12, so on 3.11 pytest fails at collection with a syntax error before a single test runs. CI runs 3.12, and 3.13 works too. Name the virtual environment `.venv` in the repository folder, because the Makefile runs `.venv/bin/python` when it exists and plain `python` otherwise.

`pytest` collects 1642 tests: 1635 pass, 3 are skipped because no FISCO BCOS node answers, and 4 are expected failures for open items 101, 109 and 110.

`make evidence` prints `58 passed, 0 failed, 8 not automated; stranger runs: 16 passed, 1 expected failing, 0 failed, 0 passes but flagged` and writes `evidence/report.md`.

`make dev` starts the API on `http://127.0.0.1:8000`. `GET /health` answers `{"status": "ok", ...}`, and FastAPI serves interactive documentation at `/docs`. [docs/api.md](docs/api.md) describes every endpoint.

None of these needs a key or a `.env` file. Only `/chat` and the live evidence runs call a model; for those, copy `.env.example` to `.env` and fill in the provider keys. The code loads only the `.env` beside the repository root, found from its own path, and never a parent folder's, so a clone made inside this folder reads its own `.env` or none, never this folder's keys.

The API is for developer machines only. It binds to `127.0.0.1` and has no accounts or sign in. One passphrase from `.env`, `LIFELINE_APP_PASSPHRASE`, locks it for the one demo student: with it set, every endpoint except `GET /health` needs it in the `X-Lifeline-Passphrase` header, compared in constant time, as [docs/api.md](docs/api.md) says under Passphrase. It is not accounts or sign in. With `LIFELINE_ENV=production` the API refuses to start unless `LIFELINE_CONFIRM_SECRET` and `LIFELINE_ANCHOR_SECRET` are set and the passphrase has at least 8 characters. [docs/deployment.md](docs/deployment.md) is the deployment guide.

## What is built

1. The mandate engine, `core/mandate.py`: rules R01 to R14 and tiers T0 to T3, in plain Python, with a signed confirmation token for every T2 action.
2. The hash chained ledger, `core/ledger.py`, with its head anchored in a signed local file by default, or on a local FISCO BCOS network from `chain/`.
3. The agent loop, `core/agent.py`, which puts the engine in front of every tool call, with conversation memory and replies in English, Portuguese and Chinese.
4. The council, `core/council.py`: five model voices and a chair written in code, advisory only.
5. Protect: the lost card rescue from S0 to S9 in `core/rescue.py`, pasted scam refusals, document request checks, the China quota structuring refusal, and the overseas cash cap.
6. Standing mandates under rules R12 and R13, reminders, and a monthly note built from the ledger alone.
7. Fake and simulated rails: Wise, a bank wire and Revolut as fakes, and Pix, UPI to PayNow and a China bank remittance as simulations, each reading its limits from the sourced knowledge base of 18 entries in `rails/knowledge/`.
8. The HTTP API in `api/main.py` and the evidence harness in `core/harness.py`.
9. The app in `app/`, lane C's frontend in plain HTML, CSS and JavaScript, which talks only to the API: the welcome, the onboarding, Home, the chat with a separate paste box and the confirmation card, the lost card rescue, the Activity record with the ledger under it, the Guide, and the Book and pay safely page. [app/README.md](app/README.md) says how to start and test it.

## Not in this repository yet

1. A real rail. `rails/wise_sandbox.py` calls Wise's sandbox, which moves no money, only when `WISE_SANDBOX_TOKEN` is set; no money moves anywhere today.
2. A Wise sandbox operation log. `make evidence-wise` writes one, and needs a sandbox token that is not set up yet.

## Documents

For readers and judges:

1. [docs/submission/README.md](docs/submission/README.md) is the submission index: each of the six items the rules ask for, and where it is.
2. [docs/technical_documentation.md](docs/technical_documentation.md) is the technical documentation for submission: the architecture, the core algorithms, the security design and the measured results, with the evidence report as its last appendix; `tests/test_technical_documentation.py` rebuilds its numbers from their sources.
3. [docs/self_assessment.md](docs/self_assessment.md) is the security and compliance self assessment: twelve areas, each with what is claimed, the tests that prove it and what is not claimed, then the known limitations; `tests/test_self_assessment.py` rebuilds its numbers from their sources.
4. [docs/technical-reference.md](docs/technical-reference.md) explains what is built and why, and ends with the open items.
5. [docs/code-walkthrough.md](docs/code-walkthrough.md) walks through every file of code.
6. [docs/api.md](docs/api.md) describes the HTTP API.
7. [docs/decisions.md](docs/decisions.md) records the product decisions, newest last.
8. [docs/stranger_test.md](docs/stranger_test.md) records twenty live tasks run as a stranger would.
9. [docs/knowledge_audit.md](docs/knowledge_audit.md) audits the knowledge base against its sources, and [rails/knowledge/README.md](rails/knowledge/README.md) sets its rules.
10. [chain/README.md](chain/README.md) says how to run the local FISCO BCOS network.

Team working files: [docs/build_program.md](docs/build_program.md), the lane A build program; [docs/i18n_review.md](docs/i18n_review.md), wording that waits for a native speaker; [docs/journal.md](docs/journal.md), which stops at 15 September; and [docs/hackathon/](docs/hackathon/), the competition's rules, schedule and forms.

## Lane map

| Path | Lane |
| --- | --- |
| `contracts/` | Lane A, the boundary between lanes |
| `core/` | Lane A |
| `api/` | Lane A |
| `chain/` | Lane A |
| `rails/` | Lane B |
| `app/` | Lane C |
| `suites/` | Shared |

## Rules

Read [CLAUDE.md](CLAUDE.md) before contributing. It holds the scope, the layout, and the rules every change must follow.

## Evidence

At `06b3c30` the report counts 66 suite entries. Of the 38 tasks, 31 pass and 7 are not automated; of the 28 attacks, 27 pass and 1 is not automated; none fails. Their runs count 79 in English, 24 in Portuguese and 26 in Chinese, a run that switches language counted under each. `evidence/` is ignored by git, so the report is not in the repository; run `make evidence`, or open the `evidence-report` artifact of the latest CI run on `main` under the repository's Actions tab.

The stranger runs replay, with a scripted model, the seventeen tasks of [docs/stranger_test.md](docs/stranger_test.md) that did not work in the live stranger test of 9 October, which judged 3 of 20 tasks worked, 12 worked badly and 5 failed. Each replay checks only what the code writes. After the fixes of pull request 43, 16 pass and 1 is still expected failing; a live model has not been judged again since.

`make evidence` plays every suite entry that has a scenario in `suites/scenarios/`, and every file in `suites/scenarios/stranger/`, against a scripted model and writes `evidence/report.md`. It makes no provider call and needs no key, and CI runs it after the tests pass, on every pull request and every push to `main`.

`make evidence-primary`, `make evidence-fallback` and `make evidence-swap` play the scenarios marked `live: true` against a real provider instead and write `evidence/report-<provider>.md`, and the swap also writes `evidence/report-swap.md` comparing the two. Each refuses to start without the provider's key. Set `LIVE_SCENARIO_LIMIT` to a number to keep a run cheap; empty or `all` means every scenario marked live, with `suites/live/hindi.yaml` beside them.

The workflow `.github/workflows/evidence-swap.yml` runs the swap by hand and once a week. It reads these repository secrets: `ANTHROPIC_API_KEY` and `DASHSCOPE_API_KEY`, which it needs, and `ANTHROPIC_MODEL`, `DASHSCOPE_MODEL`, `DASHSCOPE_BASE_URL`, `ANTHROPIC_COUNCIL_MODEL` and `DASHSCOPE_COUNCIL_MODEL`, which it uses when they are set. The values live only in GitHub secrets and `.env`. Without both keys the workflow skips every step that would call a provider and says why.
