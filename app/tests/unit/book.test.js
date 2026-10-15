import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";
import { BOOK_STRINGS } from "../../src/i18n-book.js";
import { APP_GROUPS, CHECKS, DEPOSIT } from "../../src/book.js";

const KEYS = Object.keys(BOOK_STRINGS.en);
const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");

test("the apps are the six agreed names, in alphabetical order within each group, with nothing else", () => {
  assert.deepEqual(APP_GROUPS.map((group) => group.key), ["book_group_flights", "book_group_stays", "book_group_paying"]);
  const names = new Set(APP_GROUPS.flatMap((group) => group.apps));
  assert.deepEqual([...names].sort(), ["HeyMax", "Singapore Airlines", "Skyscanner", "Trip.com", "Trivago", "YouTrip"]);
  for (const group of APP_GROUPS) {
    assert.deepEqual(group.apps, [...group.apps].sort((a, b) => a.localeCompare(b, "en")), group.key);
    assert.deepEqual(Object.keys(group).sort(), ["apps", "key"], "a name only: no link, logo, price or rating");
  }
});

test("the page says plainly that Lifeline is not partnered with or paid by any of the apps", () => {
  assert.equal(STRINGS.en.book_apps_note, "Lifeline isn't partnered with or paid by any of these apps.");
  assert.match(STRINGS.en.book_apps_order, /alphabetical/);
});

test("no label names a price, a fee, a figure or a ranking", () => {
  for (const code of ["en", "pt", "zh"]) {
    for (const key of KEYS) {
      assert.doesNotMatch(STRINGS[code][key], /\d|\$|SGD|USD|BRL|CNY|best|cheapest|top rated|recommend(?!s none)/i, `${key} in ${code}`);
    }
  }
});

test("there are four checks before paying and four before a rent deposit", () => {
  assert.equal(CHECKS.length, 4);
  assert.equal(DEPOSIT.length, 4);
  for (const key of [...CHECKS, ...DEPOSIT]) assert.ok(KEYS.includes(key), key);
});

test("every Book label exists in English, Portuguese and Chinese, with no dash, 您 and O Lifeline", () => {
  for (const code of ["pt", "zh"]) assert.deepEqual(Object.keys(BOOK_STRINGS[code]).sort(), [...KEYS].sort(), code);
  for (const code of ["en", "pt", "zh"]) {
    for (const key of KEYS) {
      assert.notEqual(STRINGS[code][key].trim(), "", `${key} in ${code}`);
      assert.doesNotMatch(STRINGS[code][key], /[‒-―]| - |--/, `${key} in ${code}`);
    }
  }
  for (const key of KEYS) assert.doesNotMatch(STRINGS.zh[key], /你/, key);
  for (const key of KEYS) assert.doesNotMatch(STRINGS.pt[key], /(^|[.!?]\s)Lifeline/, key);
});

test("app/README.md holds the Portuguese and Chinese of every Book label for a native speaker", () => {
  const readme = read("../../README.md");
  const section = readme.slice(readme.indexOf("## Waiting for a native speaker"));
  for (const code of ["pt", "zh"]) {
    for (const key of KEYS) assert.ok(section.includes(STRINGS[code][key].replaceAll("|", "\\|")), `${key} in ${code}`);
  }
});
