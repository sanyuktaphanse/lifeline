# Lifeline

Lifeline is a cross border finance agent for students studying abroad, built for the 2026 Shenzhen FinTechathon. It has two jobs. It helps the student move money across borders, and it protects the student from scams, fraud, and costly mistakes. Every action that moves money passes a plain Python mandate engine first, and Lifeline never gives investment advice.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Lane map

| Path | Lane |
| --- | --- |
| `core/` | Lane A |
| `rails/` | Lane B |
| `app/` | Lane C |
| `suites/` | Shared |

## Rules

Read [CLAUDE.md](CLAUDE.md) before contributing. It holds the scope, the layout, and the rules every change must follow.

## Evidence

`make evidence` plays every scenario in `suites/scenarios/` against a scripted model and writes `evidence/report.md`. It makes no provider call and needs no key, and CI runs it on every pull request.

`make evidence-primary`, `make evidence-fallback` and `make evidence-swap` play the scenarios marked `live: true` against a real provider instead and write `evidence/report-<provider>.md`, and the swap also writes `evidence/report-swap.md` comparing the two. Each refuses to start without the provider's key. Set `LIVE_SCENARIO_LIMIT` to a number to keep a run cheap; empty means every scenario marked live.

The workflow `.github/workflows/evidence-swap.yml` runs the swap by hand and once a week. It reads these repository secrets: `ANTHROPIC_API_KEY` and `DASHSCOPE_API_KEY`, which it needs, and `ANTHROPIC_MODEL`, `DASHSCOPE_MODEL`, `DASHSCOPE_BASE_URL`, `ANTHROPIC_COUNCIL_MODEL` and `DASHSCOPE_COUNCIL_MODEL`, which it uses when they are set. The values live only in GitHub secrets and `.env`. Without both keys the workflow skips every step and says so.
