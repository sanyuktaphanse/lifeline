# Team to do list

Person A is Sanyukta (core), person B is Joanne (rails and knowledge), person C is Pearlin (app and story). Made on 10 October 2026 and updated on 15 October 2026 from the repository, the open pull requests, `docs/release_checklist.md`, the rules and the master plan. Tick an item by changing `[ ]` to `[x]` in a pull request, and add new items under the right person.

**20 October 2026, 23:59 Beijing time** is the official deadline for both registration and submission; nothing is accepted after it.

## Where the submission stands

From `docs/release_checklist.md`, run on 13 October 2026, and the pull requests open on 15 October 2026.

| Submission item | State |
| --- | --- |
| 1. Technical documentation | Done, `docs/technical_documentation.md` |
| 2. Presentation deck, 10 minutes or less | Not started in the repository |
| 3. Demo video, 5 minutes or less | Not in the repository yet |
| 4. Source code with README, deployment and tests | Done; both CI jobs pass |
| 5. Security self assessment | Done, `docs/self_assessment.md` |
| 6. Execution evidence | The evidence report, the stranger runs and the chain record are done; the Wise sandbox log waits for a sandbox token |

The submission gate is not met yet: no two people have ticked the release checklist, and the README has not been followed on a machine none of us owns.

Open pull requests: #55 (passphrase lock, Sanyukta), #56 (app follow ups, Pearlin), #57 (product requirements document, Joanne), #58 (Wise balances, Joanne).

## Everyone

- [x] **Registration.** Sent by Joanne on 15 October 2026. It shares the 20 October deadline. Fill `international-registration-form-en.xlsx` outside the repository, never in it, and email it with each member's proof of enrolment to fintechathon@ican-x.com, subject "International Track Registration, team name, team leader name". Confirm who sends it, and that it was sent.
- [ ] Confirm at least 60% of the team are not Chinese nationals, as the rules require.
- [ ] Ask the organisers how the submission is delivered, since the rules do not say, and whether a FISCO BCOS anchor counts toward the on chain bonus for Topic C.
- [ ] Two people each tick `docs/release_checklist.md` independently, the submission gate.
- [ ] Rehearse the presentation under 10 minutes, at least twice. Due 18 October.
- [ ] Submit everything by 19 October, then update only if needed.

## Sanyukta, person A

- [ ] Merge every pull request; nobody else merges. Open now: #55, #56, #57, #58.
- [ ] Decide which AI provider and key the live demo and the video use, Anthropic or DashScope. Without a key the chat answers only from samples.
- [ ] Decide one clear demo student. Today she studies in Singapore, pays rent to a landlord in São Paulo and gets money from parents in China.
- [ ] Decide Joanne's request for `GET /balances/{user}`, the Wise sandbox balances when `WISE_SANDBOX_TOKEN` is set and the fixture balances otherwise. The rail side is #58.
- [ ] Decide Joanne's proposals: garak, NVIDIA's attack scanner, as outside security evidence, and Frankfurter, the European Central Bank's reference rates, for how much the landlord receives.
- [ ] Decide whether an entry first checked by Claude Code, `checked_by: CC`, counts as checked, so a person's initials are the first human check, not the second, before any document claims two person verification. Raised by Pearlin on 11 October.
- [ ] Decide open item 178: the fixture `wise` and `bank_wire` routes say they are not simulated, so the agent picks the fixture bank wire over the honest Wise sandbox route.
- [ ] Connect the translator to the agent so tasks T04 and T05 work, open item 181.
- [ ] Run a second stranger test against the fixes, since the model's own words can still be wrong (self assessment, limitation 3).
- [ ] Automate the tasks the evidence report lists as not automated, or cut the ones the cut list allows.
- [ ] Deck content: the story, the numbers, the demo flow. Due 16 October.
- [ ] Clean machine release check, Stage 18, rerun on the final commit. Due 18 October.
- [x] #39, #40, #42, #49 and #50 from lane B merged.
- [x] #41, lane B's submission drafts, closed on 11 October: superseded by the final documents.
- [x] Fix the conversation problems the stranger test of 9 October found: done in #43; the evidence report gives 16 of 17 stranger runs passed and 1 expected failing.
- [x] Final technical documentation, Stage 17: `docs/technical_documentation.md`, #46.
- [x] Final security self assessment, Stage 16: `docs/self_assessment.md`, #45.
- [x] Documentation truth check, Stage 15, #44, and accuracy fixes, #47.
- [x] Release: licence, submission index, chain record, app CI job and release checklist, #53.

## Joanne, person B

- [ ] Make a Wise sandbox account and API token, and put `WISE_SANDBOX_TOKEN` and `WISE_SANDBOX_PROFILE_ID` in `.env`. Then Claude Code makes the sandbox recipients and runs `make evidence-wise` for the sandbox operation log, submission item 6.
- [ ] Second check the nine China entries, `rails/knowledge/china.yaml`: open each source page and add your initials in `second_check_by`, as `docs/knowledge_audit.md` lists under "For lane B".
- [ ] Second check `sg_nus_fee_payment_003` in a browser and add initials. On 15 October 2026 the live page, with its FAQ expanded, held every sentence of the statement. Its "Third Party Payer" answer, a payment link emailed to the parent and paid within 2 weeks, is not in the entry yet and could be a new entry.
- [ ] Find a native speaker to check the Portuguese of the English only sentences in `docs/i18n_review.md` and the translator's warning, open items 156 and 172. The Chinese is checked.
- [ ] Design the presentation deck with Pearlin. Due 17 October.
- [ ] Execution evidence pack: `evidence/report.md`, `evidence/wise-sandbox.md`, the stranger runs, `chain/evidence.md` and the demo video link, in one place for the submission. Due 18 October.
- [ ] Final README after a clean machine test by Pearlin. Due 18 October.
- [ ] Update `docs/prd.md` in #57 with the decisions of 14 October.
- [ ] Share the phone first mockup on branch `joanne/mockup` with Pearlin as a reference for `app/`.
- [x] Deployment guide, `docs/deployment.md`, in #39.
- [x] Wise sandbox rail and quotes, #39, and its balances, #58.
- [x] Translator, #40.
- [x] Chinese native speaker review, #49, and the Portuguese review by SP, #50.
- [x] Chinese second checks of Pearlin's app labels on #56.
- [x] Keep the project out of iCloud: it lives in `~/Projects/lifeline`.

## Pearlin, person C

- [ ] Second check the nine Brazil, India, Singapore and provider entries. Started 11 October.
- [ ] On #56, change the Corridor label on the confirmation card, `field_corridor`, from 通道 to 汇往国家或地区, so it matches the corridor trigger.
- [ ] Bring the ideas of the mockup on branch `joanne/mockup` into `app/`, adapted to the app.
- [ ] Demo video, no more than 5 minutes, from the real software. Rough cut due 16 October, final due 18 October.
- [ ] Deck visual design with Joanne. Due 17 October.
- [ ] Clean machine test: follow the README on a computer none of us owns, and report every step that fails. Due 16 October.
- [x] The app is in the repository under `app/`, #48, connected to the API with simulated labels, #52, with a welcome, a guide and a logo, #54.
- [x] Reviewed `sg_nus_fee_payment_003` against its page and raised the parent payment route.

## After submission

- [ ] Finalists are announced by 31 October. If chosen, at least one member must attend in Shenzhen, check in 20 November, final 21 to 23 November.
