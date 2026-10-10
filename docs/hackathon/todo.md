# Team to do list

Person A is Sanyukta (core), person B is Joanne (rails and knowledge), person C is Pearlin (app and story). Made on 10 October 2026 from the repository, the rules and the master plan. Tick an item by changing `[ ]` to `[x]` in a pull request, and add new items under the right person.

Two dates matter. **15 October 2026** is the team's own deadline for the build. **20 October 2026, 23:59 Beijing time** is the official deadline for both registration and submission; nothing is accepted after it.

## Everyone, before anything else

- [ ] **Registration.** It shares the 20 October deadline. Fill `international-registration-form-en.xlsx` outside the repository, never in it, and email it with each member's proof of enrolment to fintechathon@ican-x.com, subject "International Track Registration, team name, team leader name". Confirm who sends it. Due 12 October.
- [ ] Confirm at least 60% of the team are not Chinese nationals, as the rules require.
- [ ] Ask the organisers how the submission is delivered, since the rules do not say, and whether a FISCO BCOS anchor counts toward the on chain bonus for Topic C. Due 12 October.
- [ ] Agree new freeze dates, since the master plan's fact and feature freezes on 25 October are after the deadline. Suggested: feature freeze 15 October, fact freeze 17 October, everything submitted by 19 October with a day to spare.
- [ ] Rehearse the presentation under 10 minutes, at least twice. Due 18 October.
- [ ] Submit everything by 19 October, then update only if needed.

## Sanyukta, person A

- [ ] Review and merge #39 (Wise sandbox and deployment guide; it edits `api/main.py` and `tests/conftest.py`), #40 (translator) and #41 (submission drafts). Due 11 October.
- [ ] Decide open item 168: the fixture `wise` and `bank_wire` routes say they are not simulated, so the agent picks the fixture bank wire over the honest Wise sandbox route.
- [ ] Connect the translator to the agent so tasks T04 and T05 work, open item 171.
- [ ] Fix the conversation problems the stranger test of 9 October found: 17 expected failing scenarios in `suites/scenarios/stranger/`, 5 of them failures. This is most of the task completion score, 40%. Due 15 October.
- [ ] Automate the 7 tasks not yet automated (T03, T04, T24, T25, T27, T28, T33), or cut the ones the cut list allows.
- [ ] Final technical documentation, build program Stage 17, folding in the drafts in `docs/submission/`. Due 17 October.
- [ ] Final security self assessment, Stage 16, from the draft in `docs/submission/`. Due 17 October.
- [ ] Deck content: the story, the numbers, the demo flow. Due 16 October.
- [ ] Documentation truth check, Stage 15, and the clean machine release check, Stage 18. Due 18 October.

## Joanne, person B

- [ ] Make a Wise sandbox account and API token, and put `WISE_SANDBOX_TOKEN` and `WISE_SANDBOX_PROFILE_ID` in `.env`. Then Claude Code makes the sandbox recipients and runs `make evidence-wise` for the sandbox operation log, submission item 6. Due 12 October.
- [ ] Open each of the 18 knowledge entries' source pages and add your initials in `second_check_by`, as `docs/knowledge_audit.md` lists under "For lane B". Eight of them say to check again before 16 October. Due 15 October.
- [ ] Find native speakers to check the Portuguese and Chinese of the English only sentences in `docs/i18n_review.md` and the translator's warning, open items 156 and 172. Due 16 October.
- [ ] Design the presentation deck with Pearlin. Due 17 October.
- [ ] Execution evidence pack: `evidence/report.md`, `evidence/wise-sandbox.md` and the demo video link, in one place for the submission. Due 18 October.
- [ ] Final README and deployment guide after a clean machine test by Pearlin. Due 18 October.

## Pearlin, person C

- [ ] **Put the app in the repository** under `app/`. It is not there yet, and judges score interaction from it. Due 13 October.
- [ ] Connect the app to the backend, `docs/api.md`, and show the simulated label wherever a route or receipt is simulated.
- [ ] Demo video, no more than 5 minutes, from the real software. Rough cut due 16 October, final due 18 October.
- [ ] Deck visual design with Joanne. Due 17 October.
- [ ] Clean machine test: follow the README on a computer that has never run Lifeline, and report every step that fails. Due 16 October.

## After submission

- [ ] Finalists are announced by 31 October. If chosen, at least one member must attend in Shenzhen, check in 20 November, final 21 to 23 November.
