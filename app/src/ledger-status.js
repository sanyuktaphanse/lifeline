// Turns a GET /ledger/{user_id}/verify response into the lines the ledger screen shows (docs/api.md).
// Each line names its part (chain, anchor, hold, dev), the label key, the values for it, and a tone.

export function verifyLines(verify) {
  const lines = [];
  const add = (part, key, tone, values = {}) => lines.push({ part, key, tone, values });

  if (verify.first_broken_seq === null || verify.first_broken_seq === undefined) add("chain", "chain_ok", "ok");
  else add("chain", "chain_broken", "danger", { seq: verify.first_broken_seq });

  const anchor = verify.anchor ?? {};
  if (!anchor.anchored) {
    add("anchor", "anchor_none", "warn", { kind: anchor.kind });
  } else {
    if (anchor.verified) add("anchor", "anchor_ok", "ok", { seq: anchor.head_seq, kind: anchor.kind, at: anchor.anchored_at });
    else add("anchor", "anchor_bad", "danger", { seq: anchor.head_seq, kind: anchor.kind });
    if (anchor.matches_ledger === false) add("anchor", "anchor_mismatch", "danger");
    if (anchor.error) add("anchor", "anchor_error", "danger", { error: anchor.error });
    if (anchor.block_number !== undefined && anchor.block_number !== null) add("anchor", "anchor_block", "info", { block: anchor.block_number });
  }

  if (verify.integrity_hold) add("hold", "hold_on", "danger", { reason: verify.integrity_hold.reason });
  else add("hold", "hold_none", "ok");

  if (Array.isArray(verify.development_secrets) && verify.development_secrets.length > 0) {
    add("dev", "dev_secrets", "warn", { names: verify.development_secrets.join(", ") });
  }
  return lines;
}

// A note carries its own kind in the payload, such as family_notice, which says more than "note".
export function entryLabel(entry) {
  const inner = entry.payload && typeof entry.payload.kind === "string" ? entry.payload.kind : null;
  return entry.kind === "note" && inner ? `${entry.kind}: ${inner}` : entry.kind;
}
