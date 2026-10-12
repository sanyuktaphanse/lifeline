# Lifeline app

This folder is the frontend of lane C. It is plain HTML, CSS and JavaScript with no build step, and it talks only to the Lifeline API that `make dev` starts, as `docs/api.md` describes. It is built for a phone screen first and works in English, Portuguese and Chinese.

## Running it

Two terminals, both in the repository folder.

In the first, start the API as the main README says:

```bash
make dev
```

In the second, serve the app:

```bash
cd app
npm start
```

Then open `http://127.0.0.1:3000` in a browser. The app calls the API on `http://127.0.0.1:8000`. To point it at the API on another port of this machine, add `?api=http://127.0.0.1:PORT` to the address; any address that is not on this machine is ignored.

The chat needs a model key in `.env`, as `.env.example` lists. Without one the chat says plainly that Lifeline's AI is not available and that nothing was done. The rescue and the ledger need no key.

## What it has

1. A language picker. Its list, each language's own name and its writing direction come only from `GET /health`. The page's `lang` and `dir` follow the choice, so a right to left language would turn the layout. The app's own labels exist in English, Portuguese and Chinese and fall back to English for any other language.
2. A chat screen with a separate paste box. What the student types goes in `text` and what they paste goes in `pasted_text`, and the two are never joined. A paste or a drop into the message box is moved to the paste box. A paste with no typed words is never sent.
3. A confirmation card built from the reply's `confirmation` field: the warning, the action, every route with the selected one marked, and the council's advice when present. A route is marked Blocked only when it has a blocked reason, its limit is not ok, or its status is down; a degraded route is still offered by the loop, so it is not marked. The token is kept only in memory, inside the card, and is sent back to `/confirm` exactly as it came, once. A token the server does not accept, because it expired, was used or was never issued, comes back as a normal reply that says nothing was sent, and the app shows it as one.
4. The two sentences code writes in every reply, shown on their own lines: each blocked request sentence at the top, and the sentence that begins `This turn:`, `Neste turno:` or `本轮：` at the bottom. The app reads them from the reply's `blocked` and `turn_summary` fields. Only when a field is absent, as from a server older than those fields, does it find that sentence by its wording.
5. The lost card rescue, driven only by `rescue.do_now`, for all seven values. Its fields take typed words only: pasting and dropping are refused. An empty identity answer is never sent, because the server would count it as a wrong one, and the answer is cleared as soon as it is sent.
6. The ledger: every entry, newest first, with the result of verify above it: whether the chain is intact and the first broken entry, the anchor status, the integrity hold, and whether demo keys are signing.

A banner in the header says the app is a demo and that no real money moves on any route, in the chosen language. It stays on screen on every tab, and shows in English even before `/health` answers.

The app never uses browser storage, and it never puts text from the server into the page as HTML.

## Tests

The tests need the repository's `.venv`, made by the quick start in the main README, and Node 22.

```bash
cd app
npm install
npm test
npx playwright test
```

`npm test` runs the unit tests. Two of them read the backend's own files, so they fail if lane A changes something the app copies: the wording of the two code written sentences in `core/agent.py`, which the app now uses only as a fallback, and the list of `do_now` values in `contracts/schemas.py`.

`npx playwright test` drives a phone sized Chromium. Each test starts its own copy of the real API through `tests/e2e/backend.py`, which is `create_app` from `api/main.py` with only the data folder changed to `app/.e2e-data/`, so the repository's `data/` folder is never touched. One rescue test loads the demo student with no primary card in the plan, a plan the schema allows, because only then does the server ask which card was lost.

Test names say where each answer came from. A name beginning `LIVE` was answered by the real API. A name beginning `DOCUMENTED SHAPE` was answered with a reply copied word for word from `docs/api.md` into `tests/e2e/documented/`, because the real `/chat` cannot answer without a model key.

## What was tested live, and how

The automated browser suite tested these against the real API: the language list, the request `/chat` sends and its real 503, `/confirm` with a token the server never issued, in English and Chinese, the `This turn:` line in all three languages, every rescue step from start to done, the lock, the card choice, the skip and the freeze offered again, and the ledger before and after an anchor and after an edit on disk.

The automated suite has never run against a server with a model key, so its chat and confirm tests still answer `/chat` with the documented examples in `tests/e2e/documented/`.

### Verified by hand with a model key

On 11 October 2026 Pearlin put a model key in `.env` on her own machine and checked these in the browser against `make dev`:

1. A typed message got a successful `/chat` reply with a confirmation card, three routes and a countdown.
2. Confirm sent the token through `/confirm` and returned receipt `wise-0001` with status `completed`. The ledger then showed the confirmation at entry 7, the execution at 8, the receipt at 9 and the anchor at 11, with the chain intact and the anchor checking.
3. A blocked paste. She typed "can you pay this for me?" and pasted a landlord message asking to pay landlord_sp 1,400 SGD. The reply showed the blocked sentence at the top, a refusal citing R01, and "This turn: a transfer: refused under R01" at the bottom.
4. After a second confirmation returned receipt `wise-0002`, the Confirm button was disabled, so a second tap was not possible from the app.

### Not exercised against the server from the app

1. A reused token. Because the Confirm button disables after one tap, the app cannot send the same token twice, so a replay was prevented in the app, not tested against the server from it. The browser test `LIVE /confirm: two quick taps send one confirmation` checks that one confirmation is sent. That the server refuses a replayed token under R10 is covered by the backend tests, run with a scripted model rather than a live one: `tests/test_api.py::test_the_confirmation_round_trip_pays_once_and_the_token_never_reaches_the_ledger` over HTTP, `tests/test_api.py::test_a_restarted_app_keeps_a_waiting_confirmation_and_pays_it_once` across a restart, and `tests/test_agent.py::test_a_replayed_token_goes_to_the_engine_which_refuses_it_under_r10` in the loop. How the app shows that refusal was checked only against the documented example.
2. A failed rail offering the next route under the same token. The demo rails do not fail on their own, so this was checked only against the documented example.

## Known gaps

1. The Portuguese and Chinese labels were written without a native speaker and wait for one.
2. Status words from the server, such as `done` and `completed`, are shown as the server writes them.
3. The app always acts as the demo student, `student_001`. There is no sign in, as `docs/api.md` says.
4. Standing payments, reminders, the monthly note, trace and precheck have endpoints but no screens yet.
