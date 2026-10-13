# Lifeline mockup, phone first

A redesign proposal by Joanne, beside lane C's app in `app/`, which it does not touch. It is plain HTML, CSS and JavaScript with no build step and talks only to the real Lifeline API that `make dev` starts, as `docs/api.md` describes. The team decides what of it goes into `app/`.

## Running it

Start the API as the main README says, then serve this folder, for example with Python:

```bash
.venv/bin/python -m http.server 3001 --bind 127.0.0.1 --directory mockup
```

Open `http://127.0.0.1:3001`, ideally in a phone sized window. Chat needs a model key in `.env`; Home, Lost card, Activity and Help do not.

## What is different from `app/`

1. A minimal welcome: one line at the top, the Lifeline heartbeat beeping inside a glowing orb in the middle, and Try the demo at the bottom. Face ID, Apple and Google are small icons marked coming soon, because the API has no sign in (self assessment, open item 37).
2. A welcome step after Try the demo that shows the demo student's safety net, from the demo plan `docs/api.md` describes.
3. English, Portuguese and Chinese for every label, from a picker in the header or `?lang=pt` and `?lang=zh` in the address. The chosen language is sent to the API too, so replies follow it. The Portuguese is Brazilian with "o Lifeline" and the Chinese uses 您; no native speaker has reviewed the mockup's own labels yet.
4. A floating tab bar like an iPhone app: Home, Chat, Lost card, Activity, Help.
5. Home: a greeting with a reminders bell, a large Lost card button, the next reminder from `GET /reminders`, four one tap actions, recent activity with the ledger's verify result, and a link to what is coming next.
6. Chat: message bubbles, four suggested prompts and more on request, a 📎 button for a message the student received, sent as `pasted_text` and shown as a quoted bubble, and a small beating orb while Lifeline thinks.
7. A payment sheet for every confirmation: the amount, who it goes to, why, the route, the fee, the exchange cost, when it arrives and the total, a live countdown to the token's expiry, every route behind Compare routes, and one Confirm and send.
8. Lost card: the rescue as one card with a progress bar, driven by `rescue.do_now`. Pasting is off, and the identity answer is sent once and kept nowhere.
9. Activity: the ledger in plain words with filters for payments, blocks and rescues, and a Verified badge from `GET /ledger/{user_id}/verify`; the technical entries sit behind Advanced.
10. Help, and a Coming next screen for what Topic C asks that is not built yet, such as credit building and asking family for money, each saying what exists today.
11. A 404 page where the heartbeat goes flat.
12. Black and purple frosted glass with Montserrat headings and Inter text. With Reduce transparency on, cards turn solid; with Reduce motion on, nothing moves.

## Hosted preview

When no Lifeline API answers at all, as on a Netlify link, the screens fill with sample data from `sample.js`, and the header pill says "Preview · sample data". Every sample reply carries a Sample tag and nothing moves. With the API running, the sample data is never used.

## Rules it keeps

Server text is only ever set as text, never as HTML. A confirmation token lives in memory inside its card and is sent back once. Nothing is kept in browser storage. Everything is English for now; the API's replies follow the student's language, the labels do not yet.
