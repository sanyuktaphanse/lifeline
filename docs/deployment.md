# Deployment guide

How to run Lifeline's backend on a clean machine, what each setting in `.env` does, and how to run it without reaching hosts that may be blocked in China. Lane B owns this guide. Every command below was run on a Mac with Apple silicon, the test run on 13 October 2026, except `make evidence-wise`, which waits for a sandbox token.

## 1. What you need

1. Python 3.12 or later. CI runs 3.12 (`.github/workflows/ci.yml`). On Python 3.9, the version macOS ships, `pip install` fails because several pinned packages need Python 3.10 or later, and on 3.10 or 3.11 the code's 3.12 generic syntax fails at collection. If your machine has no Python 3.12, `uv` installs one inside your user folder without an administrator password: `uv venv --python 3.12 .venv`.
2. Git, and access to the repository.
3. Optional: Docker, only for the FISCO BCOS anchor in section 6.

The app the student uses, lane C's, is in `app/`, and `app/README.md` says how to start it; this guide covers the backend the app talks to.

## 2. Install and test

From the repository root, with `python3.13` in place of `python3.12` in the first command if that is what you have:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

The suite needs no key and makes no network call: `tests/conftest.py` fails any test that reaches a real model provider and blanks the Wise sandbox token. On 15 October 2026 it gave 1635 passed, 3 skipped and 4 expected failures, 1642 collected, on branch `lane-a/final-docs`.

```bash
make evidence
```

writes `evidence/report.md`, the task and attack suites played against a scripted model. It needs no key either.

## 3. Configure

Copy `.env.example` to `.env` and fill in what you need. `.env` is ignored by git and is the only place a secret lives.

| Setting | What it does | Empty means |
| --- | --- | --- |
| `LIFELINE_ENV` | `production` makes the API refuse to start without the two secrets and the passphrase below | development |
| `LIFELINE_CONFIRM_SECRET` | Signs confirmation tokens | A public development secret, refused in production |
| `LIFELINE_ANCHOR_SECRET` | Signs the local ledger anchor | A public development secret, refused in production |
| `LIFELINE_APP_PASSPHRASE` | One passphrase that locks the API for the one demo student, sent in the `X-Lifeline-Passphrase` header and compared in constant time; not accounts or sign in | The API is unlocked; refused in production, which needs at least 8 characters |
| `MODEL_PROVIDER` | `anthropic` or `dashscope`, the model the agent uses | `anthropic` |
| `FALLBACK_MODEL_PROVIDER` | The provider tried when the first one fails | `dashscope` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Anthropic key and model | No Anthropic calls; model `claude-opus-5` |
| `DASHSCOPE_API_KEY`, `DASHSCOPE_MODEL`, `DASHSCOPE_BASE_URL` | Alibaba Cloud DashScope key, model and endpoint | No DashScope calls; model `qwen-plus` |
| `COUNCIL` | `on` convenes the five voice council for large or unusual transfers | Off |
| `ANTHROPIC_COUNCIL_MODEL`, `DASHSCOPE_COUNCIL_MODEL` | A different model for the council | The ordinary model |
| `SIM_RAILS` | `off` removes the simulated UPI to PayNow and China rails | On |
| `ANCHOR` | `local` or `fisco` | `local` |
| `FISCO_RPC_URL`, `FISCO_CONTRACT_ADDRESS`, `FISCO_KEY_PATH` | The FISCO BCOS node, contract and key | Not used unless `ANCHOR=fisco` |
| `WISE_SANDBOX_TOKEN`, `WISE_SANDBOX_PROFILE_ID`, `WISE_SANDBOX_RECIPIENTS` | The Wise sandbox, section 5 | The fixture Wise rail |
| `LIVE_SCENARIO_LIMIT` | Caps how many scenarios a live evidence run plays | Every scenario marked live |

For a demo that anyone else can reach, set `LIFELINE_ENV=production`, a passphrase of at least 8 characters, and two long random secrets, for example from `python3 -c "import secrets; print(secrets.token_hex(32))"`.

## 4. Run the API

```bash
make dev
```

starts the API on `http://127.0.0.1:8000` with reload. It accepts browser requests only from `localhost` and `127.0.0.1` on any port. Check it with:

```bash
curl http://127.0.0.1:8000/health
```

`/health` answers without the passphrase and says in `passphrase_required` whether one is set. With `LIFELINE_APP_PASSPHRASE` set, every other call needs it in a header, for example `curl -H "X-Lifeline-Passphrase: $LIFELINE_APP_PASSPHRASE" http://127.0.0.1:8000/ledger/student_001`, and is answered `401` without it; `docs/api.md`, Passphrase, gives the details. The passphrase is one shared value for the one demo student, not accounts or sign in.

The demo student is `student_001` from `fixtures/demo_user.yaml`, and a parent in India is loaded from `fixtures/demo_parent.yaml`. The ledger and the conversations are written to `data/`, which git ignores. `docs/api.md` describes every endpoint with real requests and responses.

## 5. The Wise sandbox

Without a token the `wise` rail is a fixture. With one, its quotes, transfers, traces and cancels go to Wise's sandbox at `https://api.wise-sandbox.com/2026Q4`, which moves no money, and everything it returns is marked simulated.

1. Make a Wise sandbox account and an API token from Wise's developer documentation, docs.wise.com. A person does this; the token is personal.
2. Put the token in `WISE_SANDBOX_TOKEN` and the sandbox profile's number in `WISE_SANDBOX_PROFILE_ID`.
3. Make a recipient in the sandbox for each payee the demo pays, and list them in `WISE_SANDBOX_RECIPIENTS` as `payee_id:recipient_account_id` pairs separated by commas, such as `self_sg:12345678`.
4. Top up the sandbox balance in the sending currency, because the rail funds transfers from it.
5. Run `make evidence-wise`. It writes `evidence/wise-sandbox.md`, the sandbox operation log: two transfers the demo student proposes and confirms through Lifeline's API and mandate engine, one moved through Wise's simulated statuses and one cancelled, and a check that the ledger verifies. The ledger of the run is kept in `.harness_tmp/wise-sandbox/`.

A personal sandbox account can quote and create transfers, but Wise refuses to fund them by API under its PSD2 policy, which no longer lets a personal account complete strong customer authentication with signed requests. The log of such a run is `docs/wise_sandbox_log.md`. Completing a transfer needs a business sandbox profile.

## 6. The FISCO BCOS anchor

Optional. `bash chain/setup.sh` starts a four node FISCO BCOS network in Docker, deploys the contract, and prints the four `ANCHOR` and `FISCO_` settings for `.env`. `chain/README.md` gives the details. When the chain cannot be reached, the agent writes an `anchor_failed` note and payments go on.

## 7. Running in China

The final is on site in Shenzhen, where some hosts may be unreachable.

1. Model: set `MODEL_PROVIDER=dashscope`, which is served from Alibaba Cloud, and keep Anthropic as the fallback or leave it unset. `make evidence-swap` compares the two providers on the live scenarios.
2. Anchor: use `ANCHOR=local`, or a FISCO BCOS network started on the laptop before travelling.
3. Rails: the simulated rails need no network. Leave `WISE_SANDBOX_TOKEN` empty unless the sandbox host has been checked from the venue; the fixture Wise rail then runs offline.
4. Dependencies: install from `requirements.txt` before travelling, so the laptop needs no package download on site.

Whether each host is reachable from Shenzhen has not been tested; the master plan schedules that test on a clean machine before the final.

## 8. Reset the demo

Stop the API and delete the `data/` folder to start again from an empty ledger. This deletes the demo's ledger and conversations for good, so copy the folder first if you need them.
