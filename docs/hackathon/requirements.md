# Submission requirements

What the organisers ask for, where each item lives in the repository, and who owns it. Owners follow the lanes in the master plan, section 4. The status column was checked against `main` on 10 October 2026; update it as items land.

## Checklist

| Item | Required by the rules | Where it lives | Owner | Status on 10 October |
| --- | --- | --- | --- | --- |
| 1. Technical documentation | System architecture, core algorithm description, security design | `docs/technical-reference.md` is the internal reference. The submission document is planned as `docs/technical_documentation.md`, build program Stage 17. | A, with B for the rails sections | Not yet written |
| 2. Presentation deck | For a final presentation of no more than 10 minutes | Not in the repository | A content, C design | Not started in the repository |
| 3. Demo video | Optional, no more than 5 minutes | Not in the repository | C | Not started in the repository |
| 4. Source code | README, GitHub link, deployment instructions, test cases | This repository. `README.md` has install steps. Tests are in `tests/`. A deployment guide is a lane B deliverable. | All; README and deployment guide B | Code and tests present; deployment guide missing |
| 5. Security self assessment | Permission tier implementation and known risk list | Planned as `docs/self_assessment.md`, build program Stage 16, outline in master plan section 17 | A | Not yet written |
| 6. Execution evidence | Simulated account or sandbox operation logs, and the demo video | `make evidence` writes `evidence/report.md`; CI uploads it on every pull request. Sandbox logs need the Wise sandbox rail. | B evidence pack, A harness | Scripted report runs; no sandbox logs yet |

## Scoring and what answers it

| Criterion | Weight | What in Lifeline answers it |
| --- | --- | --- |
| Task completion | 40% | The task suite in `suites/tasks.yaml` and the evidence report's pass counts |
| Security and compliance | 30% | The mandate engine and tiers, the attack suite, the ledger with verify and anchor, the self assessment |
| Innovation and interaction | 30% | The council, Protect and the rescue, three languages, the app |
| Challenge bonus | 0 to 5 points | On chain exploration. Lifeline anchors its ledger head on FISCO BCOS; whether that counts toward the bonus on Topic C is not stated in the rules. |

## Rules to keep in mind

1. Everything submitted is in English.
2. Third party code and data must be properly licensed; check before adding a dependency or a copied page.
3. The submission can be updated until the deadline, so submit early and update.
