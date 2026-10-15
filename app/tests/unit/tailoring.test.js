import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { greeting, fromHome, homeStarter, precheckFor } from "../../src/tailoring.js";

const router = readFileSync(new URL("../../../rails/fake_router.py", import.meta.url), "utf-8");
const trip = (home, study) => ({ home, study, purpose: "exchange" });

test("the greeting names the place of study, and is plain without a trip", () => {
  assert.equal(greeting(trip("BR", "SG"), "en"), "Hello. Lifeline is ready for your time in Singapore.");
  assert.equal(greeting(trip("SG", "BR"), "pt"), "Olá. O Lifeline está pronto para o seu período de estudos. Destino: Brasil.");
  assert.match(greeting(trip("BR", "CN"), "zh"), /中国/);
  assert.equal(greeting(null, "en"), "Hello. Lifeline is ready to help.");
});

test("money from home names the home country", () => {
  assert.equal(fromHome(trip("IN", "SG"), "en"), "Money from India");
  assert.equal(fromHome(null, "en"), "Money from home");
});

test("the home starter asks about money from home, by country", () => {
  assert.equal(homeStarter(trip("CN", "SG"), "en"), "My family wants to send money from China. What will the bank ask for?");
  assert.equal(homeStarter(trip("FR", "SG"), "en"), "How can my family send me money from France?");
  assert.equal(homeStarter(null, "en"), null);
});

test("the checks on Me follow the trip, and each kind is one the router answers", () => {
  assert.deepEqual(precheckFor(trip("CN", "SG")), [{ action_kind: "remit_from_china", provider: "cn_bank_remit_sim" }]);
  assert.deepEqual(precheckFor(trip("SG", "CN")), [{ action_kind: "arrive_in_china", provider: "alipay" }]);
  assert.deepEqual(precheckFor(trip("SG", "BR")), [{ action_kind: "enable_pix", provider: "sim_pix" }]);
  assert.deepEqual(precheckFor(trip("FR", "DE")), []);
  assert.deepEqual(precheckFor(null), []);
  for (const t of [trip("CN", "BR"), trip("SG", "BR"), trip("SG", "CN")]) {
    for (const check of precheckFor(t)) assert.match(router, new RegExp(`action_kind [!=]= "${check.action_kind}"`));
  }
});
