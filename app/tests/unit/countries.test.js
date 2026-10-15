import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { COUNTRIES, RULES_ON_FILE, countryGroups, countryName, flag, hasRules } from "../../src/countries.js";

const KNOWLEDGE = new URL("../../../rails/knowledge/", import.meta.url);

// The countries the knowledge base has sourced entries for, read from each entry's `country` field.
function knowledgeCountries() {
  const found = new Set();
  for (const file of readdirSync(KNOWLEDGE).filter((name) => name.endsWith(".yaml"))) {
    for (const match of readFileSync(new URL(file, KNOWLEDGE), "utf-8").matchAll(/^\s+country:\s*"?([A-Za-z]+)"?\s*$/gm)) {
      if (match[1] !== "all") found.add(match[1]);
    }
  }
  return [...found].sort();
}

test("the countries listed first are exactly the ones rails/knowledge has entries for", () => {
  assert.deepEqual([...RULES_ON_FILE].sort(), knowledgeCountries());
  assert.deepEqual([...RULES_ON_FILE].sort(), ["BR", "CN", "IN", "SG"]);
});

test("the country list holds every one of them once, as two capital letters", () => {
  assert.ok(COUNTRIES.length > 200);
  assert.equal(new Set(COUNTRIES).size, COUNTRIES.length);
  for (const code of COUNTRIES) assert.match(code, /^[A-Z]{2}$/);
  for (const code of RULES_ON_FILE) assert.ok(COUNTRIES.includes(code), code);
});

test("a flag is built from the two regional indicator letters", () => {
  assert.equal(flag("BR"), "\u{1F1E7}\u{1F1F7}");
  assert.equal(flag("SG"), "\u{1F1F8}\u{1F1EC}");
});

test("country names follow the chosen language", () => {
  assert.equal(countryName("BR", "en"), "Brazil");
  assert.equal(countryName("BR", "pt"), "Brasil");
  assert.equal(countryName("CN", "zh"), "中国");
});

test("the four with rules on file come first, by name, and the rest follow by name without them", () => {
  const groups = countryGroups("en");
  assert.deepEqual(groups.onFile.map((item) => item.code), ["BR", "CN", "IN", "SG"]);
  assert.equal(groups.others.length, COUNTRIES.length - 4);
  for (const code of RULES_ON_FILE) assert.ok(!groups.others.some((item) => item.code === code));
  const names = groups.others.map((item) => item.name);
  assert.deepEqual(names, [...names].sort((a, b) => a.localeCompare(b, "en")));
  assert.equal(groups.onFile[0].label, `${flag("BR")} Brazil`);
});

test("only the four have rules on file", () => {
  assert.ok(hasRules("CN"));
  assert.ok(!hasRules("FR"));
  assert.ok(!hasRules(null));
});
