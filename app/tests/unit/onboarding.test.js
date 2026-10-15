import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  CASH_CHOICES, PLAN_STEPS, PURPOSES, READ_ONLY_STEPS, ROUTE_CHOICES, SAMPLE_PLAN, UPDATABLE_FIELDS,
  backupChoices, composeMessage, planChanges, planOnFile, tripReady,
} from "../../src/onboarding.js";

const fixture = readFileSync(new URL("../../../fixtures/demo_user.yaml", import.meta.url), "utf-8");
const schemas = readFileSync(new URL("../../../contracts/schemas.py", import.meta.url), "utf-8");
const router = readFileSync(new URL("../../../rails/fake_router.py", import.meta.url), "utf-8");
const knowledge = readFileSync(new URL("../../../rails/knowledge/singapore.yaml", import.meta.url), "utf-8");

test("the trip is ready only with a home, a place of study and a purpose", () => {
  assert.ok(!tripReady(null));
  assert.ok(!tripReady({ home: "BR", study: "SG" }));
  assert.ok(!tripReady({ home: "BR", study: "SG", purpose: "shopping" }));
  assert.ok(tripReady({ home: "BR", study: "SG", purpose: "exchange" }));
  assert.deepEqual(PURPOSES, ["exchange", "degree", "internship", "leisure", "family", "work"]);
});

test("the steps that change the plan are exactly the four fields update_plan accepts", () => {
  const fields = schemas.match(/PLAN_UPDATE_FIELDS = \(([^)]+)\)/)[1].match(/"(\w+)"/g).map((name) => name.slice(1, -1));
  assert.deepEqual(UPDATABLE_FIELDS, fields);
  assert.deepEqual(PLAN_STEPS, ["backup_card", "backup_route", "wallet", "cash_plan", "contact", "money", "question"]);
  assert.deepEqual([...READ_ONLY_STEPS], ["contact", "money", "question"]);
});

test("the sample plan is the plan in fixtures/demo_user.yaml", () => {
  const plan = fixture.slice(fixture.indexOf("\nplan:"));
  assert.deepEqual(SAMPLE_PLAN.cards, [...plan.matchAll(/- name: (.+)\n\s+instrument_id: "([^"]+)"/g)].map((m) => ({ name: m[1], instrument_id: m[2] })));
  assert.equal(SAMPLE_PLAN.primary_instrument, plan.match(/primary_instrument: "([^"]+)"/)[1]);
  assert.equal(SAMPLE_PLAN.backup_instrument, plan.match(/backup_instrument: "([^"]+)"/)[1]);
  assert.equal(SAMPLE_PLAN.backup_route, plan.match(/backup_route: (\w+)/)[1]);
  assert.equal(SAMPLE_PLAN.wallet_token_present, plan.match(/wallet_token_present: (\w+)/)[1] === "true");
  assert.deepEqual(SAMPLE_PLAN.cash_plan, plan.match(/cash_plan: \[([^\]]*)\]/)[1].split(", "));
  assert.deepEqual(SAMPLE_PLAN.trusted_contact, { name: plan.match(/name: (\w+)\n\s+channel/)[1], channel: plan.match(/channel: (\w+)/)[1] });
  assert.equal(SAMPLE_PLAN.emergency_allowance, plan.match(/emergency_allowance: "(\d+)"/)[1]);
  assert.equal(SAMPLE_PLAN.question, plan.match(/question: (.+)\n/)[1]);
  assert.equal(SAMPLE_PLAN.currency, fixture.match(/currency: (\w+)/)[1]);
});

test("a backup can only be another of the plan's own cards, never the main card", () => {
  assert.deepEqual(backupChoices(SAMPLE_PLAN).map((card) => card.instrument_id), ["revolut:card_02"]);
});

test("the route and cash choices are ones the server can hold", () => {
  for (const rail of ROUTE_CHOICES) assert.ok(router.includes(`"${rail}"`), rail);
  assert.ok(!ROUTE_CHOICES.includes("sim_pix"));
  for (const choice of CASH_CHOICES) for (const id of choice.ids) assert.match(knowledge, new RegExp(`id: ${id}\\n`));
  assert.deepEqual(CASH_CHOICES.map((choice) => choice.ids), [["sg_cash_pickup_001"], []]);
});

test("the plan on file is the sample plan with every update the ledger executed, in order", () => {
  const ledger = [
    { seq: 3, kind: "execution", payload: { action: { type: "update_plan" }, result: { plan_updated: { backup_route: "bank_wire", wallet_token_present: false } } } },
    { seq: 6, kind: "execution", payload: { action: { type: "update_plan" }, result: { error: "The plan was not changed" } } },
    { seq: 9, kind: "execution", payload: { action: { type: "update_plan" }, result: { plan_updated: { backup_route: "wise", cash_plan: [] } } } },
    { seq: 10, kind: "proposal", payload: { result: { plan_updated: { wallet_token_present: true } } } },
  ];
  const plan = planOnFile(ledger);
  assert.equal(plan.backup_route, "wise");
  assert.equal(plan.wallet_token_present, false);
  assert.deepEqual(plan.cash_plan, []);
  assert.equal(plan.backup_instrument, "revolut:card_02");
  assert.deepEqual(planOnFile([]), SAMPLE_PLAN);
});

test("only the fields the student changed are kept", () => {
  assert.deepEqual(planChanges(SAMPLE_PLAN, { backup_instrument: "revolut:card_02", backup_route: "wise", wallet_token_present: true, cash_plan: ["sg_cash_pickup_001"] }), {});
  assert.deepEqual(planChanges(SAMPLE_PLAN, { backup_route: "bank_wire", cash_plan: [] }), { backup_route: "bank_wire", cash_plan: [] });
});

test("the message names every change in plain words with the ids the plan holds, in each language", () => {
  const changes = { backup_instrument: "revolut:card_02", backup_route: "bank_wire", wallet_token_present: false, cash_plan: ["sg_cash_pickup_001"] };
  assert.equal(
    composeMessage("en", changes, SAMPLE_PLAN),
    "Please update my plan: my backup card is my Revolut card (revolut:card_02); my backup route is Bank transfer (bank_wire); no phone wallet holds my card; my cash plan is the cash pickup in Singapore (sg_cash_pickup_001).",
  );
  assert.equal(composeMessage("en", { cash_plan: [] }, SAMPLE_PLAN), "Please update my plan: my cash plan is empty.");
  for (const lang of ["pt", "zh"]) {
    const words = composeMessage(lang, changes, SAMPLE_PLAN);
    for (const id of ["revolut:card_02", "bank_wire", "sg_cash_pickup_001"]) assert.ok(words.includes(id), `${id} in ${lang}`);
  }
  assert.equal(composeMessage("en", {}, SAMPLE_PLAN), null);
});
