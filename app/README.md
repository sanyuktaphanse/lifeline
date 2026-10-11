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
3. A confirmation card built from the reply's `confirmation` field: the warning, the action, every route with the selected one marked, and the council's advice when present. The token is kept only in memory, inside the card, and is sent back to `/confirm` exactly as it came, once. A token the server does not accept, because it expired, was used or was never issued, comes back as a normal reply that says nothing was sent, and the app shows it as one.
4. The two sentences code writes in every reply, shown on their own lines: each blocked request sentence at the top, and the sentence that begins `This turn:`, `Neste turno:` or `本轮：` at the bottom.
5. The lost card rescue, driven only by `rescue.do_now`, for all seven values. Its fields take typed words only: pasting and dropping are refused. An empty identity answer is never sent, because the server would count it as a wrong one, and the answer is cleared as soon as it is sent.
6. The ledger: every entry, newest first, with the result of verify above it: whether the chain is intact and the first broken entry, the anchor status, the integrity hold, and whether demo keys are signing.

The app never uses browser storage, and it never puts text from the server into the page as HTML.

## Tests

The tests need the repository's `.venv`, made by the quick start in the main README, and Node 22.

```bash
cd app
npm install
npm test
npx playwright test
```

`npm test` runs the unit tests. Two of them read the backend's own files, so they fail if lane A changes something the app copies: the wording of the two code written sentences in `core/agent.py`, and the list of `do_now` values in `contracts/schemas.py`.

`npx playwright test` drives a phone sized Chromium. Each test starts its own copy of the real API through `tests/e2e/backend.py`, which is `create_app` from `api/main.py` with only the data folder changed to `app/.e2e-data/`, so the repository's `data/` folder is never touched. One rescue test loads the demo student with no primary card in the plan, a plan the schema allows, because only then does the server ask which card was lost.

Test names say where each answer came from. A name beginning `LIVE` was answered by the real API. A name beginning `DOCUMENTED SHAPE` was answered with a reply copied word for word from `docs/api.md` into `tests/e2e/documented/`, because the real `/chat` cannot answer without a model key.

## What has not been tested against a live server

These were built to the shapes in `docs/api.md` and checked only against those documented examples:

1. A successful `/chat` reply of any kind.
2. The blocked request sentence at the top of a reply, which only `/chat` with pasted text produces.
3. A transfer confirmed through `/confirm` that pays and returns a receipt, a reused token refused under R10, and a failed rail offering the next route under the same token.

What was tested live: the language list, the request `/chat` sends and its real 503, `/confirm` with a token the server never issued, in English and Chinese, the `This turn:` line in all three languages, every rescue step from start to done, the lock, the card choice, the skip and the freeze offered again, and the ledger before and after an anchor and after an edit on disk.

## Known gaps

1. The API has no field for the two code written sentences, so the app finds them by their wording. A field in the reply from lane A would remove that dependence.
2. The Portuguese and Chinese labels were written without a native speaker and wait for one.
3. Status words from the server, such as `done` and `completed`, are shown as the server writes them.
4. The app always acts as the demo student, `student_001`. There is no sign in, as `docs/api.md` says.
5. Standing payments, reminders, the monthly note, trace and precheck have endpoints but no screens yet.
