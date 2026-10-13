import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";
import { WELCOME_CARDS, GUIDE_SECTIONS, PROTECT_SECTIONS, NEW_KEYS } from "../../src/guide-content.js";
import { LOGO_PATH } from "../../src/logo.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");

test("every new key exists in English, Portuguese and Chinese, and is not empty", () => {
  assert.ok(NEW_KEYS.length > 40);
  for (const code of ["en", "pt", "zh"]) {
    for (const key of NEW_KEYS) {
      assert.equal(typeof STRINGS[code][key], "string", `${key} missing in ${code}`);
      assert.notEqual(STRINGS[code][key].trim(), "", `${key} empty in ${code}`);
    }
  }
});

test("every key the welcome and the guide draw is a new key", () => {
  const drawn = [
    ...WELCOME_CARDS.flatMap((card) => [card.title, ...card.lines]),
    ...[...GUIDE_SECTIONS, ...PROTECT_SECTIONS].flatMap((section) => [section.title, ...section.lines, ...(section.examples ?? [])]),
  ];
  for (const key of drawn) assert.ok(NEW_KEYS.includes(key), `${key} is drawn but not listed`);
});

test("the welcome has three cards and the guide its six sections, then the six security sections", () => {
  assert.equal(WELCOME_CARDS.length, 3);
  assert.equal(GUIDE_SECTIONS.length, 6);
  for (const section of GUIDE_SECTIONS) assert.ok(section.lines.length >= 2 && section.lines.length <= 4, section.id);
  assert.deepEqual(
    PROTECT_SECTIONS.map((section) => STRINGS.en[section.title]),
    ["What decides", "What you confirm", "What can never start an action", "What is recorded", "What Lifeline does not do", "What this demo is"],
  );
});

test("the security sections keep the agreed English wording", () => {
  const body = (id) => PROTECT_SECTIONS.find((section) => section.id === id).lines.map((key) => STRINGS.en[key]).join(" ");
  assert.equal(
    body("decides"),
    "The model proposes. The engine decides. A rail executes. The ledger records. Every action passes a plain Python engine with fourteen rules before anything happens, and no model is ever asked whether an action is allowed.",
  );
  assert.equal(
    body("confirm"),
    "A payment, a new payee, a card freeze, setting up a standing payment and a cancellation run only after you confirm a token bound to that exact action, which expires in five minutes and can be used once. After that, a standing payment's runs go ahead on their own, only within the pattern you confirmed.",
  );
  assert.equal(
    body("never"),
    "Anything you paste, anything a provider sends back. Lifeline reads it as information, refuses an action that comes only from it, and tells you at the top of the reply.",
  );
  assert.match(body("recorded"), /on a FISCO BCOS chain when Lifeline is set to use one,/);
  assert.match(body("demo"), /docs\/self_assessment\.md/);
});

test("the guide names neither Flywire nor Convera, and the rent example is the agreed sentence", () => {
  for (const code of ["en", "pt", "zh"]) {
    for (const key of NEW_KEYS) assert.doesNotMatch(STRINGS[code][key], /Flywire|Convera/, `${key} in ${code}`);
  }
  assert.equal(STRINGS.en.guide_ex_rent, "Send this month's rent of 1,200 SGD to my landlord in Brazil");
});

test("the favicon in index.html draws the same pulse as the logo", () => {
  const html = read("../../index.html");
  const favicon = html.match(/<link rel="icon" href="data:image\/svg\+xml,([^"]+)"/);
  assert.ok(favicon, "no SVG favicon");
  assert.ok(decodeURIComponent(favicon[1]).includes(LOGO_PATH));
});

test("app/README.md holds the Portuguese and Chinese of every new text for a native speaker", () => {
  const readme = read("../../README.md");
  const section = readme.slice(readme.indexOf("## Waiting for a native speaker"));
  assert.ok(section.length > 0 && readme.includes("## Waiting for a native speaker"));
  for (const code of ["pt", "zh"]) {
    for (const key of NEW_KEYS) assert.ok(section.includes(STRINGS[code][key].replaceAll("|", "\\|")), `${key} in ${code}`);
  }
});
