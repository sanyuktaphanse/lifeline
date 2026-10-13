# Team to do list

Person A is Sanyukta (core), person B is Joanne (rails and knowledge), person C is Pearlin (app and story). Made on 10 October 2026 and updated on 11 October 2026 from the repository, the rules and the master plan. Tick an item by changing `[ ]` to `[x]` in a pull request, and add new items under the right person.

Two dates matter. **15 October 2026** is the team's own deadline for the build. **20 October 2026, 23:59 Beijing time** is the official deadline for both registration and submission; nothing is accepted after it.

## Everyone, before anything else

- [ ] **Registration.** It shares the 20 October deadline. Fill `international-registration-form-en.xlsx` outside the repository, never in it, and email it with each member's proof of enrolment to fintechathon@ican-x.com, subject "International Track Registration, team name, team leader name". Confirm who sends it. Due 12 October.
- [ ] Confirm at least 60% of the team are not Chinese nationals, as the rules require.
- [ ] Ask the organisers how the submission is delivered, since the rules do not say, and whether a FISCO BCOS anchor counts toward the on chain bonus for Topic C. Due 12 October.
- [ ] Agree new freeze dates, since the master plan's fact and feature freezes on 25 October are after the deadline. Suggested: feature freeze 15 October, fact freeze 17 October, everything submitted by 19 October with a day to spare.
- [ ] Rehearse the presentation under 10 minutes, at least twice. Due 18 October.
- [ ] Submit everything by 19 October, then update only if needed.

## Sanyukta, person A

- [ ] Decide whether an entry first checked by Claude Code, `checked_by: CC`, counts as checked, so a person's initials are the first human check, not the second, before any document claims two person verification. Raised by Pearlin on 11 October.
- [ ] Merge every pull request; nobody else merges. Order for lane B: #39, then #40, then #42.

- [ ] Review and merge #39 (Wise sandbox and deployment guide; it edits `api/main.py` and `tests/conftest.py`), then #40 (translator), in that order, because both change the test count the documents state. Due 11 October.
- [x] #41, lane B's submission drafts, closed on 11 October: superseded by the final documents.
- [ ] Decide open item 178, numbered 168 before the renumbering: the fixture `wise` and `bank_wire` routes say they are not simulated, so the agent picks the fixture bank wire over the honest Wise sandbox route.
- [ ] Connect the translator to the agent so tasks T04 and T05 work, open item 181.
- [x] Fix the conversation problems the stranger test of 9 October found: done in #43; the evidence report now gives 16 of 17 stranger runs passed and 1 expected failing.
- [ ] Run a second stranger test against the fixes, since the model's own words can still be wrong (self assessment, limitation 3). Due 15 October.
- [ ] Automate the 7 tasks not yet automated (T03, T04, T24, T25, T27, T28, T33), or cut the ones the cut list allows.
- [x] Final technical documentation, Stage 17: `docs/technical_documentation.md`, #46.
- [x] Final security self assessment, Stage 16: `docs/self_assessment.md`, #45.
- [ ] Deck content: the story, the numbers, the demo flow. Due 16 October.
- [x] Documentation truth check, Stage 15, #44, and accuracy fixes, #47.
- [ ] Clean machine release check, Stage 18. Due 18 October.

## Joanne, person B

- [ ] Rewrite `sg_nus_fee_payment_003` from the live NUS page with Pearlin's findings, and fix what depends on it, task T36 and the China tuition refusal. Due 13 October.
- [ ] Ask Pearlin whether the app exists and has run against the API, for Sanyukta.

- [ ] Make a Wise sandbox account and API token, and put `WISE_SANDBOX_TOKEN` and `WISE_SANDBOX_PROFILE_ID` in `.env`. Then Claude Code makes the sandbox recipients and runs `make evidence-wise` for the sandbox operation log, submission item 6. Due 12 October.
- [ ] Second check the nine China entries, `rails/knowledge/china.yaml`: open each source page and add your initials in `second_check_by`, as `docs/knowledge_audit.md` lists under "For lane B". Pearlin takes the other nine. Due 14 October.
- [ ] Find native speakers to check the Portuguese and Chinese of the English only sentences in `docs/i18n_review.md` and the translator's warning, open items 156 and 172. Due 16 October.
- [ ] Design the presentation deck with Pearlin. Due 17 October.
- [ ] Execution evidence pack: `evidence/report.md`, `evidence/wise-sandbox.md` and the demo video link, in one place for the submission. Due 18 October.
- [x] Deployment guide written, `docs/deployment.md`, in #39.
- [ ] Final README after a clean machine test by Pearlin. Due 18 October.
- [ ] Keep the project out of iCloud: a copy on an iCloud synced Desktop or Documents folder hangs tests and corrupts git. Use a folder such as `~/Projects`.

## Pearlin, person C

- [ ] Second check the nine Brazil, India, Singapore and provider entries. Started 11 October.
- [x] Found that `sg_nus_fee_payment_003` does not match its page: NUS lists Flywire and Convera beside PayNow QR and cards rather than strongly recommending them, and a third party payment is a payer link emailed to the parent, with no KYC and no relationship documents. Not initialled.

- [ ] **Put the app in the repository** under `app/`. It is not there yet, and judges score interaction from it. Due 13 October.
- [ ] Connect the app to the backend, `docs/api.md`, and show the simulated label wherever a route or receipt is simulated.
- [ ] Demo video, no more than 5 minutes, from the real software. Rough cut due 16 October, final due 18 October.
- [ ] Deck visual design with Joanne. Due 17 October.
- [ ] Clean machine test: follow the README on a computer that has never run Lifeline, and report every step that fails. Due 16 October.

## After submission

- [ ] Finalists are announced by 31 October. If chosen, at least one member must attend in Shenzhen, check in 20 November, final 21 to 23 November.
