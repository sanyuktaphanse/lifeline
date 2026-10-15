import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { friendlyEntries, groupByDay, payeeKey } from "../../src/activity.js";

const fixture = readFileSync(new URL("../../../fixtures/demo_user.yaml", import.meta.url), "utf-8");
const at = (hour) => new Date(2026, 9, 15, hour).toISOString();
const transfer = { type: "transfer", idempotency_key: "k3", amount: "300", currency: "SGD", payee_id: "self_sg", purpose: "emergency" };

// Shaped like the entries the real API wrote for a rescue, a payment and a precheck on 15 October 2026.
const LEDGER = [
  { seq: 1, ts: at(9), kind: "note", payload: { kind: "rescue_started", trigger: "card_lost" } },
  { seq: 2, ts: at(9), kind: "note", payload: { kind: "rescue_transition", from: "S0", to: "S1" } },
  { seq: 3, ts: at(9), kind: "turn", payload: { messages: 0 } },
  { seq: 12, ts: at(9), kind: "execution", payload: { action: { type: "freeze_card" }, result: { freeze: { status: "done" } } } },
  { seq: 22, ts: at(10), kind: "proposal", payload: { tool: "propose_transfer", action: transfer } },
  { seq: 25, ts: at(10), kind: "anchor", payload: { head_seq: 24 } },
  { seq: 27, ts: at(10), kind: "execution", payload: { action: transfer } },
  { seq: 28, ts: at(10), kind: "receipt", payload: { rail: "wise", receipt: { receipt_id: "wise-0001", rail: "wise", amount: "300", currency: "SGD", status: "completed", idempotency_key: "k3", simulated: false } } },
  { seq: 30, ts: at(11), kind: "note", payload: { kind: "rescue_replacement", estimate_id: "sg_card_replacement_002" } },
  { seq: 35, ts: at(11), kind: "note", payload: { kind: "family_notice", to: { name: "Ana", channel: "whatsapp" } } },
  { seq: 41, ts: at(12), kind: "decision", payload: { decision: { allowed: false, rule_ids: ["R01"] }, idempotency_key: "k9" } },
  { seq: 42, ts: at(12), kind: "proposal", payload: { action: { type: "transfer", idempotency_key: "k10" } } },
  { seq: 43, ts: at(12), kind: "decision", payload: { decision: { allowed: false, rule_ids: ["R05"] }, idempotency_key: "k10" } },
  { seq: 44, ts: at(13), kind: "execution", payload: { action: { type: "precheck" }, result: { precheck: {} } } },
  { seq: 45, ts: at(13), kind: "receipt", payload: { receipt: { receipt_id: "sim_pix-0001", rail: "sim_pix", amount: "1200", currency: "SGD", status: "pending", idempotency_key: "k11", simulated: true } } },
];

test("each entry a student would recognise becomes one plain line, newest first, with its ledger seq", () => {
  const rows = friendlyEntries(LEDGER);
  assert.deepEqual(rows.map((row) => [row.seq, row.key]), [
    [45, "act_sent_status"],
    [44, "act_precheck"],
    [43, "act_refused"],
    [41, "act_refused_paste"],
    [35, "act_family_told"],
    [30, "act_replacement"],
    [28, "act_sent"],
    [12, "act_frozen"],
    [1, "act_rescue_started"],
  ]);
});

test("a payment names the amount and the payee its proposal held, and says when it was simulated", () => {
  const rows = friendlyEntries(LEDGER);
  const sent = rows.find((row) => row.seq === 28);
  assert.deepEqual(sent.values, { amount: "300", currency: "SGD", payee: "self_sg" });
  assert.equal(sent.simulated, false);
  const pending = rows.find((row) => row.seq === 45);
  assert.deepEqual(pending.values, { amount: "1200", currency: "SGD", payee: null, status: "pending" });
  assert.equal(pending.simulated, true);
});

test("a refusal names the action type, and the family notice names the contact and channel", () => {
  const rows = friendlyEntries(LEDGER);
  assert.deepEqual(rows.find((row) => row.seq === 43).values, { type: "transfer" });
  assert.deepEqual(rows.find((row) => row.seq === 35).values, { name: "Ana", channel: "whatsapp" });
  assert.equal(rows.find((row) => row.seq === 43).tone, "bad");
});

test("a plan update the ledger executed names the fields it changed, and a failed one is left out", () => {
  const rows = friendlyEntries([
    { seq: 3, ts: at(9), kind: "execution", payload: { action: { type: "update_plan" }, result: { plan_updated: { backup_route: "bank_wire", cash_plan: [] } } } },
    { seq: 6, ts: at(9), kind: "execution", payload: { action: { type: "update_plan" }, result: { error: "The plan was not changed" } } },
  ]);
  assert.deepEqual(rows.map((row) => [row.seq, row.key, row.values]), [[3, "act_plan_updated", { fields: ["backup_route", "cash_plan"] }]]);
});

test("a freeze that did not finish says its status", () => {
  const rows = friendlyEntries([{ seq: 5, ts: at(9), kind: "execution", payload: { result: { freeze: { status: "not_supported" } } } }]);
  assert.deepEqual(rows.map((row) => [row.key, row.values]), [["act_freeze_status", { status: "not_supported" }]]);
});

test("rows are grouped under Today, Yesterday or the date, in local time", () => {
  const now = new Date(2026, 9, 15, 18);
  const rows = [
    { seq: 3, ts: new Date(2026, 9, 15, 1).toISOString() },
    { seq: 2, ts: new Date(2026, 9, 14, 23).toISOString() },
    { seq: 1, ts: new Date(2026, 9, 2, 12).toISOString() },
  ];
  const groups = groupByDay(rows, now, "en");
  assert.deepEqual(groups.map((group) => [group.key ?? group.date, group.rows.map((row) => row.seq)]), [
    ["activity_today", [3]],
    ["activity_yesterday", [2]],
    ["2 Oct", [1]],
  ]);
  assert.equal(groupByDay(rows, now, "pt")[2].date, "2 de out.");
});

test("the payees with plain names are the demo mandate's own", () => {
  const payees = fixture.match(/allowed_payees: \[(.+)\]/)[1].split(", ");
  for (const payee of payees) assert.equal(payeeKey(payee), `payee_${payee}`);
  assert.equal(payeeKey("someone_else"), null);
});
