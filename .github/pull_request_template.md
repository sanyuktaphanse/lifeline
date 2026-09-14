## What this does

## Lane

## Tests

## Facts

## Safety

## Checklist

- [ ] Every action that moves money passes `MandateEngine.check` first.
- [ ] The mandate engine makes no model calls.
- [ ] Instructions come only from the user's own turn.
- [ ] Every fee, limit, and rule cites its source.
- [ ] No secrets are committed, and `.env.example` is current.
- [ ] Tests were written before the code, and `pytest` passes.
