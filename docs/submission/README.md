# Lifeline submission index

Lifeline is a cross border finance agent for students studying abroad, entered in the International Track of the 2026 Shenzhen FinTechathon under Topic C. This page maps each of the six items the rules ask for, in `docs/hackathon/rules.md` section 5, to where it is in this repository. It describes `main` at commit `06b3c30`, 13 October 2026, with the release pull request that adds this page.

| Item the rules ask for | Where it is |
| --- | --- |
| 1. Technical documentation: system architecture, core algorithm description, security design | [docs/technical_documentation.md](../technical_documentation.md) |
| 2. Presentation deck | Attached to the submission form; it is not in the repository. |
| 3. Demo video, no more than 5 minutes | Attached to the submission form; it is not in the repository. |
| 4. Source code with README, repository link, deployment instructions and test cases | This repository, https://github.com/sanyuktaphanse/lifeline, public since 15 October 2026, so anyone can clone it: [README.md](../../README.md), [docs/deployment.md](../deployment.md), the backend tests in [tests/](../../tests/) and the app tests in [app/tests/](../../app/tests/) |
| 5. Security self assessment: permission tier implementation and known risk list | [docs/self_assessment.md](../self_assessment.md) |
| 6. Execution evidence: simulated account or sandbox operation logs | `evidence/report.md`, which `make evidence` writes and CI uploads as the `evidence-report` artifact on every run whose tests pass; the stranger runs in [suites/scenarios/stranger/](../../suites/scenarios/stranger/) and the live stranger test they replay, [docs/stranger_test.md](../stranger_test.md); and the chain record, [chain/evidence.md](../../chain/evidence.md) |

No money moves anywhere: every rail is a fixture or a simulation, and the Wise sandbox log that `make evidence-wise` writes is pending a sandbox token.

## How to check this yourself

These are the five commands of the self assessment's How to check this yourself. Python 3.12 or later is required; use `python3.13 -m venv .venv` in the second command if that is what you have.

```bash
git clone https://github.com/sanyuktaphanse/lifeline.git
cd lifeline && python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest
make evidence
python -c "from core.harness import evaluate; r=[e for e in evaluate() if e.suite=='attacks']; print(len(r), 'attacks,', sum(e.status=='passed' for e in r), 'passed, not passed:', [e.id+' '+e.status for e in r if e.status!='passed'])"
```

[docs/self_assessment.md](../self_assessment.md) says what each prints. [app/README.md](../../app/README.md) says how to start the app and run its tests.
