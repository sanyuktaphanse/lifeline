# Lifeline

Lifeline is a cross border finance agent for students studying abroad, built for the 2026 Shenzhen FinTechathon. It has two jobs. It helps the student move money across borders, and it protects the student from scams, fraud, and costly mistakes. Every action that moves money passes a plain Python mandate engine first. Lifeline is instructed never to give investment advice; one sentence of the system prompt carries that rule, and no code checks the model's words, as open item 170 of the technical reference records.

This README describes `main` at commit `c824610`, 10 October 2026. The repository is https://github.com/sanyuktaphanse/lifeline.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
make evidence
make dev
```

CI runs Python 3.12, and 3.13 works too. Name the virtual environment `.venv` in the repository folder, because the Makefile runs `.venv/bin/python` when it exists and plain `python` otherwise.

`pytest` collects 1480 tests: 1473 pass, 3 are skipped because no FISCO BCOS node answers, and 4 are expected failures for open items 101, 109 and 110.

`make evidence` prints `58 passed, 0 failed, 8 not automated; stranger runs: 16 passed, 1 expected failing, 0 failed, 0 passes but flagged` and writes `evidence/report.md`.

`make dev` starts the API on `http://127.0.0.1:8000`. `GET /health` answers `{"status": "ok", ...}`, and FastAPI serves interactive documentation at `/docs`. [docs/api.md](docs/api.md) describes every endpoint.

None of these needs a key or a `.env` file. Only `/chat` and the live evidence runs call a model; for those, copy `.env.example` to `.env` and fill in the provider keys. The code loads `.env` from the current folder or any folder above it, so a clone made inside this folder with no `.env` of its own reads this folder's keys; give such a clone its own empty `.env`, as open item 173 explains.

The API is for developer machines only. It binds to `127.0.0.1` and has no sign in. With `LIFELINE_ENV=production` it refuses to start unless `LIFELINE_CONFIRM_SECRET` and `LIFELINE_ANCHOR_SECRET` are set. A deployment guide is a lane B deliverable and is not written yet.

## What is built

1. The mandate engine, `core/mandate.py`: rules R01 to R14 and tiers T0 to T3, in plain Python, with a signed confirmation token for every T2 action.
2. The hash chained ledger, `core/ledger.py`, with its head anchored in a signed local file by default, or on a local FISCO BCOS network from `chain/`.
3. The agent loop, `core/agent.py`, which puts the engine in front of every tool call, with conversation memory and replies in English, Portuguese and Chinese.
4. The council, `core/council.py`: five model voices and a chair written in code, advisory only.
5. Protect: the lost card rescue from S0 to S9 in `core/rescue.py`, pasted scam refusals, document request checks, the China quota structuring refusal, and the overseas cash cap.
6. Standing mandates under rules R12 and R13, reminders, and a monthly note built from the ledger alone.
7. Fake and simulated rails: Wise, a bank wire and Revolut as fakes, and Pix, UPI to PayNow and a China bank remittance as simulations, each reading its limits from the sourced knowledge base of 18 entries in `rails/knowledge/`.
8. The HTTP API in `api/main.py` and the evidence harness in `core/harness.py`.

## Not in this repository yet

1. The frontend. Lane C builds it against the API.
2. A real rail. The Wise sandbox rail is in review as pull request 39; no money moves anywhere today.
3. The security self assessment and the technical documentation for submission, build program Stages 16 and 17. Until then the technical reference sections Tiers, The mandate engine, and Attacks attempted and held, and its open items, are the security design and the known risks.
4. A deployment guide.

## Documents

For readers and judges:

1. [docs/technical-reference.md](docs/technical-reference.md) explains what is built and why, and ends with the open items.
2. [docs/code-walkthrough.md](docs/code-walkthrough.md) walks through every file of code.
3. [docs/api.md](docs/api.md) describes the HTTP API.
4. [docs/decisions.md](docs/decisions.md) records the product decisions, newest last.
5. [docs/stranger_test.md](docs/stranger_test.md) records twenty live tasks run as a stranger would.
6. [docs/knowledge_audit.md](docs/knowledge_audit.md) audits the knowledge base against its sources, and [rails/knowledge/README.md](rails/knowledge/README.md) sets its rules.
7. [chain/README.md](chain/README.md) says how to run the local FISCO BCOS network.

Team working files: [docs/build_program.md](docs/build_program.md), the lane A build program; [docs/i18n_review.md](docs/i18n_review.md), wording that waits for a native speaker; [docs/journal.md](docs/journal.md), which stops at 15 September; and [docs/hackathon/](docs/hackathon/), the competition's rules, schedule and forms.

## Lane map

| Path | Lane |
| --- | --- |
| `contracts/` | Lane A, the boundary between lanes |
| `core/` | Lane A |
| `api/` | Lane A |
| `chain/` | Lane A |
| `rails/` | Lane B |
| The frontend, not in this repository | Lane C |
| `suites/` | Shared |

## Rules

Read [CLAUDE.md](CLAUDE.md) before contributing. It holds the scope, the layout, and the rules every change must follow.

## Evidence

At `c824610` the report counts 66 suite entries. Of the 38 tasks, 31 pass and 7 are not automated; of the 28 attacks, 27 pass and 1 is not automated; none fails. Their runs count 79 in English, 24 in Portuguese and 26 in Chinese, a run that switches language counted under each. `evidence/` is ignored by git, so the report is not in the repository; run `make evidence`, or open the `evidence-report` artifact of the latest CI run on `main` under the repository's Actions tab.

The stranger runs replay, with a scripted model, the seventeen tasks of [docs/stranger_test.md](docs/stranger_test.md) that did not work in the live stranger test of 9 October, which judged 3 of 20 tasks worked, 12 worked badly and 5 failed. Each replay checks only what the code writes. After the fixes of pull request 43, 16 pass and 1 is still expected failing; a live model has not been judged again since.

`make evidence` plays every suite entry that has a scenario in `suites/scenarios/`, and every file in `suites/scenarios/stranger/`, against a scripted model and writes `evidence/report.md`. It makes no provider call and needs no key, and CI runs it on every pull request and every push to `main`.

`make evidence-primary`, `make evidence-fallback` and `make evidence-swap` play the scenarios marked `live: true` against a real provider instead and write `evidence/report-<provider>.md`, and the swap also writes `evidence/report-swap.md` comparing the two. Each refuses to start without the provider's key. Set `LIVE_SCENARIO_LIMIT` to a number to keep a run cheap; empty or `all` means every scenario marked live, with `suites/live/hindi.yaml` beside them.

The workflow `.github/workflows/evidence-swap.yml` runs the swap by hand and once a week. It reads these repository secrets: `ANTHROPIC_API_KEY` and `DASHSCOPE_API_KEY`, which it needs, and `ANTHROPIC_MODEL`, `DASHSCOPE_MODEL`, `DASHSCOPE_BASE_URL`, `ANTHROPIC_COUNCIL_MODEL` and `DASHSCOPE_COUNCIL_MODEL`, which it uses when they are set. The values live only in GitHub secrets and `.env`. Without both keys the workflow skips every step that would call a provider and says why.
