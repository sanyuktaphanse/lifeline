import { test } from "node:test";
import assert from "node:assert/strict";
import { languagesFromHealth, uiLang } from "../../src/languages.js";
import { STRINGS, t } from "../../src/i18n.js";

const HEALTH = {
  status: "ok",
  languages: {
    en: { direction: "ltr", name: "English" },
    pt: { direction: "ltr", name: "Português" },
    zh: { direction: "ltr", name: "中文" },
  },
};

test("the language list is exactly what /health sends, in its order", () => {
  assert.deepEqual(languagesFromHealth(HEALTH), [
    { code: "en", name: "English", direction: "ltr" },
    { code: "pt", name: "Português", direction: "ltr" },
    { code: "zh", name: "中文", direction: "ltr" },
  ]);
});

test("a language the app has never heard of still appears, with its own direction", () => {
  const health = { status: "ok", languages: { ...HEALTH.languages, ar: { direction: "rtl", name: "العربية" } } };
  assert.deepEqual(languagesFromHealth(health).at(-1), { code: "ar", name: "العربية", direction: "rtl" });
});

test("a direction that is neither ltr nor rtl is read as ltr", () => {
  const health = { status: "ok", languages: { xx: { direction: "sideways", name: "X" } } };
  assert.equal(languagesFromHealth(health)[0].direction, "ltr");
});

test("a missing or broken languages field gives an empty list, never a made up one", () => {
  assert.deepEqual(languagesFromHealth({ status: "ok" }), []);
  assert.deepEqual(languagesFromHealth(null), []);
});

test("the app's own labels fall back to English for a language it has no labels for", () => {
  assert.equal(uiLang("zh"), "zh");
  assert.equal(uiLang("ar"), "en");
  assert.equal(t("ar", "tab_chat"), STRINGS.en.tab_chat);
});

test("every label exists in English, Portuguese and Chinese", () => {
  const keys = Object.keys(STRINGS.en).sort();
  for (const code of ["pt", "zh"]) {
    assert.deepEqual(Object.keys(STRINGS[code]).sort(), keys, `labels missing or extra in ${code}`);
  }
});

test("a placeholder in a label is filled", () => {
  assert.match(t("en", "expires_in", { seconds: 42 }), /42/);
});
