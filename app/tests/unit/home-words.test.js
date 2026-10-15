import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";
import { HOME_STRINGS } from "../../src/i18n-home.js";
import { QUICK_ANSWERS } from "../../src/rescue-quick.js";

const KEYS = Object.keys(HOME_STRINGS.en);
const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");

test("every Home, Activity, chat and Lost card label exists in English, Portuguese and Chinese", () => {
  assert.ok(KEYS.length > 30);
  for (const code of ["pt", "zh"]) assert.deepEqual(Object.keys(HOME_STRINGS[code]).sort(), [...KEYS].sort(), code);
  for (const code of ["en", "pt", "zh"]) for (const key of KEYS) assert.notEqual(STRINGS[code][key].trim(), "", `${key} in ${code}`);
});

test("no new label uses a dash, the Chinese says 您, and the Portuguese says O Lifeline", () => {
  for (const code of ["en", "pt", "zh"]) {
    for (const key of KEYS) assert.doesNotMatch(STRINGS[code][key], /[‒-―]| - |--/, `${key} in ${code}`);
  }
  for (const key of KEYS) assert.doesNotMatch(STRINGS.zh[key], /你/, key);
  for (const key of KEYS) assert.doesNotMatch(STRINGS.pt[key], /(^|[.!?]\s)Lifeline/, key);
});

test("the one tap answers fill the box with words for a lost card and for a stolen one", () => {
  assert.deepEqual(Object.keys(QUICK_ANSWERS), ["card_lost", "card_stolen"]);
  assert.deepEqual(QUICK_ANSWERS.card_lost.map((key) => STRINGS.en[key]), ["I lost it on transport", "I left it somewhere", "I can't find it"]);
  assert.deepEqual(QUICK_ANSWERS.card_stolen.map((key) => STRINGS.en[key]), ["It was taken from my bag", "My phone and card were taken"]);
});

test("the Guide points to the ledger under Advanced on the Activity tab", () => {
  assert.equal(STRINGS.en.protect_recorded_3, "You can open every entry under Advanced on the Activity tab.");
});

test("app/README.md holds the Portuguese and Chinese of every new label for a native speaker", () => {
  const readme = read("../../README.md");
  const section = readme.slice(readme.indexOf("## Waiting for a native speaker"));
  for (const code of ["pt", "zh"]) {
    for (const key of [...KEYS, "protect_recorded_3"]) assert.ok(section.includes(STRINGS[code][key].replaceAll("|", "\\|")), `${key} in ${code}`);
  }
});
