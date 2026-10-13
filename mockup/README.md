# Lifeline mockup, phone first

A redesign proposal by Joanne, beside lane C's app in `app/`, which it does not touch. It is plain HTML, CSS and JavaScript with no build step and talks only to the real Lifeline API that `make dev` starts, as `docs/api.md` describes. The team decides what of it goes into `app/`.

## Running it

Start the API as the main README says, then serve this folder, for example with Python:

```bash
.venv/bin/python -m http.server 3001 --bind 127.0.0.1 --directory mockup
```

Open `http://127.0.0.1:3001`, ideally in a phone sized window. Chat needs a model key in `.env`; Home, Lost card, Activity and Help do not.

## What is different from `app/`

1. A welcome and sign in screen with three intro slides. It is designed in full, but the API has no sign in (self assessment, open item 37), so only "Try the demo" works; Face ID, Apple and Google say Coming soon, so the screen never claims a sign in that does not exist.
2. A bottom tab bar like an iPhone app: Home, Chat, Lost card, Activity, Help.
3. Home: the next reminder from `GET /reminders`, a large Lost card button, four one tap actions, and recent activity with the ledger's verify result.
4. Chat: message bubbles, four suggested prompts and more on request, and a 📎 button for a message the student received, sent as `pasted_text` and shown as a quoted bubble. A paste into the message box moves there, as in `app/`.
5. Lost card: the rescue as one card with a progress bar, driven by `rescue.do_now`. Pasting is off, and the identity answer is sent once and kept nowhere.
6. Activity: the ledger in plain words, receipts, blocks, freezes and rescue steps, with a "Verified" badge from `GET /ledger/{user_id}/verify`; the technical entries sit behind "Advanced".
7. Help replaces the Welcome button and the Guide tab.
8. A light frosted glass look with the Poppins font. With "Reduce transparency" on, cards turn solid.

## Rules it keeps

Server text is only ever set as text, never as HTML. A confirmation token lives in memory inside its card and is sent back once. Nothing is kept in browser storage. Everything is English for now; the API's replies follow the student's language, the labels do not yet.
