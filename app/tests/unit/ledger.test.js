import { test } from "node:test";
import assert from "node:assert/strict";
import { entryLabel, verifyLines } from "../../src/ledger-status.js";

// The three /verify responses docs/api.md shows.
const BEFORE_ANCHOR = { first_broken_seq: null, anchor: { anchored: false, kind: "local" }, integrity_hold: null, development_secrets: [] };
const AFTER_PAYMENT = {
  first_broken_seq: null,
  anchor: {
    anchored: true,
    head_hash: "9007632c329e17bf20352c8dcae33048dd1e4c2e73657c051a8540ab9328b432",
    head_seq: 7,
    verified: true,
    matches_ledger: true,
    anchored_at: "2026-10-08T11:44:57.806133+00:00",
    kind: "local",
  },
  integrity_hold: null,
  development_secrets: [],
};
const TAMPERED = {
  first_broken_seq: 1,
  anchor: { ...AFTER_PAYMENT.anchor, anchored_at: "2026-10-08T21:18:39.385717+00:00" },
  integrity_hold: { first_broken_seq: 1, reason: "The ledger chain breaks at entry 1." },
  development_secrets: [],
};

const keys = (lines) => lines.map((line) => [line.part, line.key, line.tone]);

test("before anything is anchored", () => {
  assert.deepEqual(keys(verifyLines(BEFORE_ANCHOR)), [
    ["chain", "chain_ok", "ok"],
    ["anchor", "anchor_none", "warn"],
    ["hold", "hold_none", "ok"],
  ]);
  assert.deepEqual(verifyLines(BEFORE_ANCHOR)[1].values, { kind: "local" });
});

test("after a payment the anchor checks", () => {
  const lines = verifyLines(AFTER_PAYMENT);
  assert.deepEqual(keys(lines), [
    ["chain", "chain_ok", "ok"],
    ["anchor", "anchor_ok", "ok"],
    ["hold", "hold_none", "ok"],
  ]);
  assert.deepEqual(lines[1].values, { seq: 7, kind: "local", at: "2026-10-08T11:44:57.806133+00:00" });
});

test("a tampered ledger shows where the chain breaks and that payments are paused, even while the anchor checks", () => {
  const lines = verifyLines(TAMPERED);
  assert.deepEqual(keys(lines), [
    ["chain", "chain_broken", "danger"],
    ["anchor", "anchor_ok", "ok"],
    ["hold", "hold_on", "danger"],
  ]);
  assert.deepEqual(lines[0].values, { seq: 1 });
  assert.deepEqual(lines[2].values, { reason: "The ledger chain breaks at entry 1." });
});

test("an anchor that does not check, a store that disagrees, an unreadable store and a chain block are each named", () => {
  const lines = verifyLines({
    first_broken_seq: null,
    anchor: { anchored: true, head_seq: 4, verified: false, matches_ledger: false, kind: "fisco", block_number: 12, error: "no answer" },
    integrity_hold: { first_broken_seq: null, reason: "The anchor store disagrees." },
    development_secrets: [],
  });
  assert.deepEqual(keys(lines), [
    ["chain", "chain_ok", "ok"],
    ["anchor", "anchor_bad", "danger"],
    ["anchor", "anchor_mismatch", "danger"],
    ["anchor", "anchor_error", "danger"],
    ["anchor", "anchor_block", "info"],
    ["hold", "hold_on", "danger"],
  ]);
});

test("development secrets are named so the demo is never mistaken for production", () => {
  const lines = verifyLines({ ...BEFORE_ANCHOR, development_secrets: ["LIFELINE_ANCHOR_SECRET", "LIFELINE_CONFIRM_SECRET"] });
  assert.deepEqual(lines.at(-1), { part: "dev", key: "dev_secrets", tone: "warn", values: { names: "LIFELINE_ANCHOR_SECRET, LIFELINE_CONFIRM_SECRET" } });
});

test("a note entry is named by its own kind as well", () => {
  assert.equal(entryLabel({ kind: "note", payload: { kind: "family_notice" } }), "note: family_notice");
  assert.equal(entryLabel({ kind: "decision", payload: {} }), "decision");
});
