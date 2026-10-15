import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";
import { ONBOARDING_KEYS } from "../../src/onboarding.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");
const fixture = read("../../../fixtures/demo_user.yaml");

test("every onboarding, tailoring and Me label exists in English, Portuguese and Chinese", () => {
  assert.ok(ONBOARDING_KEYS.length > 50);
  for (const code of ["en", "pt", "zh"]) {
    for (const key of ONBOARDING_KEYS) {
      assert.equal(typeof STRINGS[code][key], "string", `${key} missing in ${code}`);
      assert.notEqual(STRINGS[code][key].trim(), "", `${key} empty in ${code}`);
    }
  }
});

test("no new label uses a dash, the Chinese says 您, and the Portuguese says O Lifeline", () => {
  for (const code of ["en", "pt", "zh"]) {
    for (const key of ONBOARDING_KEYS) assert.doesNotMatch(STRINGS[code][key], /[‒-―]| - |--/, `${key} in ${code}`);
  }
  for (const key of ONBOARDING_KEYS) assert.doesNotMatch(STRINGS.zh[key], /你/, key);
  for (const key of ONBOARDING_KEYS) assert.doesNotMatch(STRINGS.pt[key], /(^|[.!?]\s)Lifeline/, key);
});

test("the onboarding says plainly that the live rescue asks the sample plan's question", () => {
  const question = fixture.match(/question: (.+)\n/)[1];
  assert.ok(STRINGS.en.onb_rescue_note.includes(question));
  assert.match(STRINGS.en.onb_rescue_note, /sample plan/);
});

test("the read only steps say what is on file, that chat cannot change it, and that a limit is tier 3", () => {
  assert.match(STRINGS.en.onb_contact_ro, /only a name and a channel, never a phone number or an email/);
  assert.match(STRINGS.en.onb_money_why, /Changing a limit is never done in chat: it is tier 3 by design\./);
  for (const key of ["onb_contact_why", "onb_money_why", "onb_question_why"]) assert.match(STRINGS.en[key], /rule R04/, key);
});

test("the onboarding never asks for a phone, an email or a safety answer any more", () => {
  for (const key of ["onb_contact_phone", "onb_contact_email", "onb_answer", "onb_answer_note", "me_on_device"]) {
    assert.ok(!ONBOARDING_KEYS.includes(key), key);
    for (const code of ["en", "pt", "zh"]) assert.equal(STRINGS[code][key], undefined, `${key} in ${code}`);
  }
});

test("the route wording is the agreed true sentence", () => {
  assert.equal(
    STRINGS.en.me_route_rule,
    "Lifeline picks the cheapest route not marked Simulated. Simulated routes follow a real rail's rules, for practice.",
  );
});

test("Me says sign in is coming soon and claims no account", () => {
  assert.match(STRINGS.en.me_signin, /coming soon/i);
  for (const key of ONBOARDING_KEYS) assert.doesNotMatch(STRINGS.en[key], /signed in|your account/i, key);
});

test("app/README.md holds the Portuguese and Chinese of every new label for a native speaker", () => {
  const readme = read("../../README.md");
  const section = readme.slice(readme.indexOf("## Waiting for a native speaker"));
  for (const code of ["pt", "zh"]) {
    for (const key of ONBOARDING_KEYS) assert.ok(section.includes(STRINGS[code][key].replaceAll("|", "\\|")), `${key} in ${code}`);
  }
});
