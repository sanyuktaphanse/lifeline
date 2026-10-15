import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  CHANNELS, EMERGENCY_CHOICES, PLAN_STEPS, PURPOSES, RELATIONSHIPS, SAFETY_QUESTIONS, SAMPLE_PLAN,
  cardChoices, planContact, setAnswer, stepReady, tripReady,
} from "../../src/onboarding.js";

const fixture = readFileSync(new URL("../../../fixtures/demo_user.yaml", import.meta.url), "utf-8");

test("the trip is ready only with a home, a place of study and a purpose", () => {
  assert.ok(!tripReady(null));
  assert.ok(!tripReady({ home: "BR", study: "SG" }));
  assert.ok(!tripReady({ home: "BR", study: "SG", purpose: "shopping" }));
  assert.ok(tripReady({ home: "BR", study: "SG", purpose: "exchange" }));
  assert.deepEqual(PURPOSES, ["exchange", "degree", "internship", "leisure", "family", "work"]);
});

test("the safety net has five steps in order", () => {
  assert.deepEqual(PLAN_STEPS, ["card", "backup", "question", "contact", "money"]);
});

test("the Singapore cards are offered only for study in Singapore, and never ranked", () => {
  const names = (trip) => cardChoices(trip).map((card) => card.id);
  assert.deepEqual(names({ study: "SG" }), ["wise", "revolut", "youtrip", "dbs_posb", "ocbc", "uob", "home_card", "unsure"]);
  assert.deepEqual(names({ study: "BR" }), ["wise", "revolut", "home_card", "unsure"]);
  assert.deepEqual(names(null), ["wise", "revolut", "youtrip", "dbs_posb", "ocbc", "uob", "home_card", "unsure"]);
  assert.equal(cardChoices(null).find((card) => card.id === "dbs_posb").name, "DBS / POSB");
});

test("each step is ready only when it is answered", () => {
  assert.ok(!stepReady("card", {}));
  assert.ok(stepReady("card", { card: "unsure" }));
  assert.ok(!stepReady("card", { card: "visa_gold" }));
  assert.ok(!stepReady("backup", {}));
  assert.ok(stepReady("backup", { backup: false }));
  assert.ok(!stepReady("question", { question: SAFETY_QUESTIONS[0] }));
  assert.ok(stepReady("question", { question: SAFETY_QUESTIONS[0], answerSet: true }));
  assert.ok(!stepReady("contact", { contact: { name: "  ", relationship: "parent", channel: "whatsapp" } }));
  assert.ok(stepReady("contact", { contact: { name: "Mei", relationship: "parent", channel: "whatsapp" } }));
  assert.ok(!stepReady("contact", { contact: { name: "Mei", relationship: "parent", channel: "carrier_pigeon" } }));
  assert.ok(stepReady("money", { money: "none" }));
  assert.ok(stepReady("money", { money: "300" }));
  assert.ok(!stepReady("money", { money: "5000" }));
});

test("the typed answer is never kept, only that one was set", () => {
  const draft = setAnswer({ question: SAFETY_QUESTIONS[0] }, "  7Q2K ");
  assert.equal(draft.answerSet, true);
  assert.ok(!JSON.stringify(draft).includes("7Q2K"));
  assert.equal(setAnswer({}, "   ").answerSet, false);
});

test("the plan's trusted contact holds only a name and a channel; phone and email stay apart", () => {
  const contact = { name: "Mei", relationship: "parent", channel: "wechat", phone: "+86 138 0000 0000", email: "mei@example.com" };
  assert.deepEqual(planContact(contact), { name: "Mei", channel: "wechat" });
  assert.ok(RELATIONSHIPS.length >= 4 && CHANNELS.includes("whatsapp"));
});

test("the sample plan is the one in fixtures/demo_user.yaml, which the live rescue reads", () => {
  assert.equal(SAMPLE_PLAN.question, fixture.match(/question: (.+)\n/)[1]);
  assert.equal(SAMPLE_PLAN.contact.name, fixture.match(/trusted_contact:\n\s+name: (\S+)/)[1]);
  assert.equal(SAMPLE_PLAN.contact.channel, fixture.match(/trusted_contact:\n\s+name: \S+\n\s+channel: (\S+)/)[1]);
  assert.equal(SAMPLE_PLAN.money, fixture.match(/emergency_allowance: "(\d+)"/)[1]);
  assert.equal(SAMPLE_PLAN.currency, fixture.match(/currency: (\w+)/)[1]);
  assert.deepEqual(SAMPLE_PLAN.cards, [...fixture.matchAll(/- name: (.+)\n\s+instrument_id/g)].map((match) => match[1]));
  assert.ok(EMERGENCY_CHOICES.includes(SAMPLE_PLAN.money));
  assert.deepEqual(EMERGENCY_CHOICES, ["100", "200", "300", "none"]);
});
