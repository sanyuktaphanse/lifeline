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
