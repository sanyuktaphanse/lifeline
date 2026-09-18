# Lifeline API

This document describes the HTTP API in `api/main.py`, which the Next.js app in lane C builds against. Every example below is a real response, recorded through FastAPI's test client with a scripted model, so the shapes are exactly what the app will receive. Only the times, hashes, and token differ from run to run.

## Running it

```bash
make dev
```

The API listens on `http://localhost:8000`. FastAPI also serves interactive documentation at `http://localhost:8000/docs` and the machine readable schema at `http://localhost:8000/openapi.json`.

`/chat` calls the model named in `.env`, so it needs `ANTHROPIC_API_KEY` or `DASHSCOPE_API_KEY` there, as `.env.example` lists. Every other endpoint works without keys. The router and the rails are fakes, so no real money moves and every fee is a fixture.

There is one demo user, `student_001`, loaded from `fixtures/demo_user.yaml` when the API starts: an SGD mandate with a per transaction limit of 1,500, a daily limit of 2,500, the payee `landlord_sp`, the corridor `SG>BR`, the purpose `rent`, and balances of 2,300 SGD and 150 BRL. Everything lives in memory. Restarting the API starts the ledger, the pending confirmations, and the mandate again from the fixture.

CORS allows `http://localhost` and `http://127.0.0.1` on any port, for `GET` and `POST` with a `Content-Type` header. No other origin is allowed.

## Conventions

1. Requests and responses are JSON.
2. Amounts are strings, such as `"1200"` or `"5.60"`, because they are exact decimals. Parse them as decimals, never as floating point numbers.
3. Times are ISO 8601 in UTC.
4. `lang` is `en`, `pt`, or `zh`. When `/chat` gets no `lang`, the language is detected from the text.
5. A confirmation token appears in exactly one place: `confirmation.confirmation_token` in a `/chat` response. It is never in `decision`, never in `/confirm` responses, and never in the ledger. Hold it in memory only, and send it back to `/confirm` when the student says yes.

## Reading an AgentReply

`/chat` and `/confirm` both return an `AgentReply`. Show `text` to the student in every case, then look at the other fields in this order.

| Field present | What happened | What to show |
| --- | --- | --- |
| `receipt` | Money moved | The receipt; if `receipt.simulated` is true, `text` already says it was a simulation |
| `freeze` | A card freeze ran | `freeze.status`: `done`, `not_supported` with `freeze.deep_link` to the issuer's app, or `failed` with `freeze.reason` |
| `confirmation` | An action waits for the student's yes | The warning for `confirmation.warning_key`, the action, and for a transfer the routes with `selected_route` marked, then a confirm button |
| `decision` with `allowed` false | The mandate engine refused | `decision.rule_ids` and `decision.reasons` |
| none of these | An answer | `text` only |

The warning keys are `warn.transfer.irreversible`, `warn.payee.new`, and `warn.freeze.card`. Translate them in the app. `ledger_seqs` lists the ledger entries this reply wrote, so the app can link to them. `provider` and `model` name the model that answered.

## GET /health

Response `200`:

```json
{
  "status": "ok"
}
```

## POST /chat

One message from the student.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_id` | string | yes | `student_001` in the demo |
| `text` | string | yes | 1 to 4,000 characters |
| `lang` | string | no | `en`, `pt`, or `zh`; detected when absent |

Request:

```json
{
  "user_id": "student_001",
  "text": "Send 1,200 SGD rent to landlord_sp in Brazil",
  "lang": "en"
}
```

Response `200`, a transfer waiting for confirmation:

```json
{
  "text": "Please confirm: send 1200 SGD to landlord_sp for rent over wise, fee 5.60 SGD and exchange cost 0 SGD. Nothing moves until you confirm.",
  "lang": "en",
  "confirmation": {
    "action": {
      "type": "transfer",
      "source": "user_turn",
      "idempotency_key": "student_001:t1:propose_transfer:1",
      "requested_at": "2026-09-18T07:48:04.555054Z",
      "amount": "1200",
      "currency": "SGD",
      "corridor": "SG>BR",
      "payee_id": "landlord_sp",
      "purpose": "rent",
      "instrument_id": null,
      "confirmation_token": null
    },
    "confirmation_token": "42d046aaa09c785c8e0ea68e463562102b32120b6091bf121d8518c60c48568a",
    "warning_key": "warn.transfer.irreversible",
    "routes": [
      {
        "rail": "wise",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "5.60",
        "spread_cost": "0",
        "tax_lines": [],
        "arrival_hours": 24.0,
        "status": "up",
        "simulated": false,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.555231Z"
      },
      {
        "rail": "sim_pix",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "0",
        "spread_cost": "0",
        "tax_lines": [],
        "arrival_hours": 1.0,
        "status": "up",
        "simulated": true,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.555231Z"
      },
      {
        "rail": "bank_wire",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "25",
        "spread_cost": "30.00",
        "tax_lines": [],
        "arrival_hours": 72.0,
        "status": "up",
        "simulated": false,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.555231Z"
      }
    ],
    "selected_route": {
      "rail": "wise",
      "corridor": "SG>BR",
      "amount": "1200",
      "currency_from": "SGD",
      "currency_to": "BRL",
      "fee": "5.60",
      "spread_cost": "0",
      "tax_lines": [],
      "arrival_hours": 24.0,
      "status": "up",
      "simulated": false,
      "limit_ok": true,
      "blocked_reason": null,
      "rule_id": null,
      "fee_source_url": null,
      "rate_source": "fixture",
      "quoted_at": "2026-09-18T07:48:04.555231Z"
    },
    "expires_in_seconds": 300
  },
  "decision": {
    "allowed": true,
    "reasons": [],
    "rule_ids": [
      "R11"
    ],
    "tier": "T2",
    "requires_confirmation": true,
    "warning_key": "warn.transfer.irreversible",
    "confirmation_token": null
  },
  "receipt": null,
  "freeze": null,
  "ledger_seqs": [
    1,
    2
  ],
  "provider": "anthropic",
  "model": "claude-opus-5"
}
```

The token to keep is `confirmation.confirmation_token`. It expires after `expires_in_seconds`, 300 seconds.

## POST /confirm

The student's yes to a waiting confirmation.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_id` | string | yes | |
| `confirmation_token` | string | yes | From the `/chat` response |
| `lang` | string | no | The language of the reply; English when absent |

Request:

```json
{
  "user_id": "student_001",
  "confirmation_token": "<the token from /chat>",
  "lang": "en"
}
```

Response `200`, the payment made:

```json
{
  "text": "Done. 1200 SGD was sent over wise. Receipt fake-0001.",
  "lang": "en",
  "confirmation": null,
  "decision": {
    "allowed": true,
    "reasons": [],
    "rule_ids": [
      "R11"
    ],
    "tier": "T2",
    "requires_confirmation": false,
    "warning_key": "warn.transfer.irreversible",
    "confirmation_token": null
  },
  "receipt": {
    "receipt_id": "fake-0001",
    "rail": "wise",
    "amount": "1200",
    "currency": "SGD",
    "status": "completed",
    "stage_entered_at": "2026-09-18T07:48:04.556629Z",
    "mandate_ref": "mandate-student_001-v1",
    "idempotency_key": "student_001:t1:propose_transfer:1",
    "simulated": false,
    "executed_at": "2026-09-18T07:48:04.556629Z"
  },
  "freeze": null,
  "ledger_seqs": [
    3,
    4,
    5
  ],
  "provider": "anthropic",
  "model": "claude-opus-5"
}
```

Response `200` when the token is unknown, already used, or expired. Nothing was sent:

```json
{
  "text": "That confirmation was not found, so nothing was sent.",
  "lang": "en",
  "confirmation": null,
  "decision": null,
  "receipt": null,
  "freeze": null,
  "ledger_seqs": [],
  "provider": null,
  "model": null
}
```

Response `200` when the rail failed and nothing was charged. The reply offers the next route under the same token, so confirm again with the token you already hold. `confirmation.confirmation_token` is an empty string here, because the token is never sent back on `/confirm`:

```json
{
  "text": "wise failed and nothing was charged under student_001:t1:propose_transfer:1. The next best route is bank_wire, fee 25 SGD. Confirm to send over it.",
  "lang": "en",
  "confirmation": {
    "action": {
      "type": "transfer",
      "source": "user_turn",
      "idempotency_key": "student_001:t1:propose_transfer:1",
      "requested_at": "2026-09-18T07:48:04.565684Z",
      "amount": "1200",
      "currency": "SGD",
      "corridor": "SG>BR",
      "payee_id": "landlord_sp",
      "purpose": "rent",
      "instrument_id": null,
      "confirmation_token": null
    },
    "confirmation_token": "",
    "warning_key": "warn.transfer.irreversible",
    "routes": [
      {
        "rail": "wise",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "5.60",
        "spread_cost": "0",
        "tax_lines": [],
        "arrival_hours": 24.0,
        "status": "up",
        "simulated": false,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.566620Z"
      },
      {
        "rail": "sim_pix",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "0",
        "spread_cost": "0",
        "tax_lines": [],
        "arrival_hours": 1.0,
        "status": "up",
        "simulated": true,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.566620Z"
      },
      {
        "rail": "bank_wire",
        "corridor": "SG>BR",
        "amount": "1200",
        "currency_from": "SGD",
        "currency_to": "BRL",
        "fee": "25",
        "spread_cost": "30.00",
        "tax_lines": [],
        "arrival_hours": 72.0,
        "status": "up",
        "simulated": false,
        "limit_ok": true,
        "blocked_reason": null,
        "rule_id": null,
        "fee_source_url": null,
        "rate_source": "fixture",
        "quoted_at": "2026-09-18T07:48:04.566620Z"
      }
    ],
    "selected_route": {
      "rail": "bank_wire",
      "corridor": "SG>BR",
      "amount": "1200",
      "currency_from": "SGD",
      "currency_to": "BRL",
      "fee": "25",
      "spread_cost": "30.00",
      "tax_lines": [],
      "arrival_hours": 72.0,
      "status": "up",
      "simulated": false,
      "limit_ok": true,
      "blocked_reason": null,
      "rule_id": null,
      "fee_source_url": null,
      "rate_source": "fixture",
      "quoted_at": "2026-09-18T07:48:04.566620Z"
    },
    "expires_in_seconds": 300
  },
  "decision": null,
  "receipt": null,
  "freeze": null,
  "ledger_seqs": [
    3,
    4
  ],
  "provider": "anthropic",
  "model": "claude-opus-5"
}
```

## GET /ledger/{user_id}

Every ledger entry for that student, oldest first. Each entry's `hash` covers its content and the previous entry's hash. Response `200`, showing the first two entries of the list:

```json
[
  {
    "seq": 1,
    "ts": "2026-09-18T07:48:04.555114Z",
    "actor": "agent",
    "kind": "proposal",
    "payload": {
      "user_id": "student_001",
      "turn": 1,
      "tool": "propose_transfer",
      "arguments": {
        "amount": "1200",
        "currency": "SGD",
        "corridor": "SG>BR",
        "payee_id": "landlord_sp",
        "purpose": "rent"
      },
      "action": {
        "type": "transfer",
        "source": "user_turn",
        "idempotency_key": "student_001:t1:propose_transfer:1",
        "requested_at": "2026-09-18T07:48:04.555054Z",
        "amount": "1200",
        "currency": "SGD",
        "corridor": "SG>BR",
        "payee_id": "landlord_sp",
        "purpose": "rent",
        "instrument_id": null
      },
      "provider": "anthropic",
      "model": "claude-opus-5",
      "mandate_id": "mandate-student_001-v1"
    },
    "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "hash": "c76dc1e12bd5c1018297dd1bff4441d02a5c17ced6be0f3ca25d04799d53b7d2"
  },
  {
    "seq": 2,
    "ts": "2026-09-18T07:48:04.555208Z",
    "actor": "agent",
    "kind": "decision",
    "payload": {
      "user_id": "student_001",
      "turn": 1,
      "idempotency_key": "student_001:t1:propose_transfer:1",
      "decision": {
        "allowed": true,
        "reasons": [],
        "rule_ids": [
          "R11"
        ],
        "tier": "T2",
        "requires_confirmation": true,
        "warning_key": "warn.transfer.irreversible"
      },
      "provider": "anthropic",
      "model": "claude-opus-5",
      "mandate_id": "mandate-student_001-v1"
    },
    "prev_hash": "c76dc1e12bd5c1018297dd1bff4441d02a5c17ced6be0f3ca25d04799d53b7d2",
    "hash": "d3d9eee2fe90a81cd22192daf4654ffe555398a4a56b9265bcdcbda6557f1e9f"
  }
]
```

The entry kinds are `proposal`, `decision`, `confirmation`, `execution`, `receipt`, `note`, and `injection_suspected`. Every payload carries `user_id`, `turn`, and `mandate_id`, and `provider` and `model` when a model answered.

## GET /ledger/{user_id}/verify

Checks the whole hash chain. `first_broken_seq` is `null` when every entry is intact, or the sequence number of the first entry that was changed. Response `200`:

```json
{
  "first_broken_seq": null
}
```

## POST /trace

Where a transfer is, by receipt id. It runs through the mandate engine and is written to the ledger like any other action. Only receipts issued to this student can be traced.

Request:

```json
{
  "user_id": "student_001",
  "receipt_id": "fake-0001"
}
```

Response `200`:

```json
{
  "receipt_id": "fake-0001",
  "status": "in_transit",
  "stage_entered_at": "2026-09-18T07:48:04.539160Z",
  "typical_duration_hours": 24.0,
  "typical_duration_source": "fixture",
  "next_steps": [
    "Wait for the recipient bank to credit the payment."
  ],
  "warnings": []
}
```

Response `404` for a receipt this student does not hold, or one the rail has no status for:

```json
{
  "detail": "No receipt fake-0404 was issued for this student."
}
```

## POST /precheck

What a provider is likely to ask for before an action, such as enabling Pix. It runs through the mandate engine and is written to the ledger.

Request:

```json
{
  "user_id": "student_001",
  "action_kind": "enable_pix",
  "provider": "sim_pix"
}
```

Response `200`:

```json
{
  "provider": "sim_pix",
  "action_kind": "enable_pix",
  "documents_likely": [
    "passport",
    "CPF number"
  ],
  "review_triggers": [
    "first Pix key registered on a foreign passport"
  ],
  "ready": null,
  "rule_ids": []
}
```

An `action_kind` the router knows nothing about returns empty lists and `ready` null, not an error.

## Errors

| Status | When | Body |
| --- | --- | --- |
| `404` | The `user_id` is not known, on every endpoint | `{"detail": "No user <id>."}` |
| `404` | `/trace` for a receipt this student does not hold | `{"detail": "<reason>"}` |
| `403` | `/trace` or `/precheck` refused by the mandate engine | `{"detail": {"rule_ids": [...], "reasons": [...]}}` |
| `422` | A field is missing, has the wrong type, or `text` is empty or too long | FastAPI's validation detail |
| `503` | `/chat` could not reach a model, such as a missing key | `{"detail": "<reason>"}` |

Unknown user, `404`:

```json
{
  "detail": "No user nobody."
}
```

Empty text, `422`:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "text"
      ],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {
        "min_length": 1
      }
    }
  ]
}
```

No model available, `503`:

```json
{
  "detail": "ANTHROPIC_API_KEY is not set. Add it to .env to use anthropic."
}
```

A refusal by the mandate engine is not an HTTP error. It comes back as `200` with `decision.allowed` false, because the student needs to read why.
