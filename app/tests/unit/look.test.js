import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";
import { LOOK_STRINGS } from "../../src/i18n-look.js";
import { ICONS } from "../../src/icons.js";
import { slideDone } from "../../src/slider.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");
const css = read("../../styles.css");
const KEYS = Object.keys(LOOK_STRINGS.en);

// The colour tokens of one :root block, as written in styles.css.
function tokens(block) {
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
}
const light = tokens(css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {"))));
const darkStart = css.indexOf('@media (prefers-color-scheme: dark)');
const dark = tokens(css.slice(darkStart, css.indexOf("}", css.indexOf(":root", darkStart))));

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a, b) => {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
function hue(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}

test("the light theme is cream and white with an indigo violet accent", () => {
  assert.equal(light.bg.toUpperCase(), "#FAF7F2");
  assert.equal(light.surface.toUpperCase(), "#FFFFFF");
  assert.equal(light.accent.toUpperCase(), "#5B3FD6");
  for (const theme of [light, dark]) {
    const h = hue(theme.accent);
    assert.ok(h >= 240 && h <= 275, `accent hue ${h}`);
  }
});

test("text, muted text, links and buttons keep a contrast of at least 4.5 to 1 in both themes", () => {
  for (const [name, theme] of [["light", light], ["dark", dark]]) {
    for (const [fg, bg] of [["text", "bg"], ["text", "surface"], ["muted", "bg"], ["muted", "surface"], ["accent", "bg"], ["accent", "surface"], ["accent-text", "accent"], ["danger-line", "danger-bg"], ["ok-line", "ok-bg"]]) {
      assert.ok(contrast(theme[fg], theme[bg]) >= 4.5, `${name}: ${fg} on ${bg} is ${contrast(theme[fg], theme[bg]).toFixed(2)}`);
    }
  }
});

test("the app loads nothing from outside: system fonts, no web font, no outside address", () => {
  const html = read("../../index.html");
  for (const [name, text] of [["index.html", html], ["styles.css", css]]) {
    // An SVG namespace names a format and loads nothing, so it is left out of the check.
    assert.doesNotMatch(text.replaceAll("xmlns='http://www.w3.org/2000/svg'", ""), /https?:\/\//, name);
    assert.doesNotMatch(text, /@import|@font-face|fonts\.googleapis|fonts\.gstatic/, name);
    assert.doesNotMatch(text.replace(/url\("?data:[^)]*\)/g, ""), /url\(/, name);
  }
  assert.match(css, /font: 16px\/1\.5 system-ui,/);
});

test("the icons are Lucide's, credited under the ISC licence in the file and in docs/licences.md", () => {
  const source = read("../../src/icons.js");
  assert.match(source, /ISC License/);
  assert.match(source, /Lucide Contributors 2022/);
  assert.match(source, /Cole Bemis 2013-2022/);
  const licences = read("../../../docs/licences.md");
  assert.match(licences, /Lucide/);
  assert.match(licences, /ISC/);
  assert.match(licences, /app\/src\/icons\.js/);
});

test("each icon is fixed line markup only, and every icon the app draws exists", () => {
  for (const [name, markup] of Object.entries(ICONS)) {
    assert.match(markup, /^(<(path|circle|rect|line|polyline) [^<>]*\/>)+$/, name);
  }
  const used = new Set();
  for (const dir of ["../../src/", "../../src/views/"]) {
    for (const file of readdirSync(new URL(dir, import.meta.url)).filter((f) => f.endsWith(".js"))) {
      const text = read(dir + file);
      for (const m of text.matchAll(/\bicon\("(\w+)"/g)) used.add(m[1]);
      // Icons named in a table such as TAB_ICONS, and drawn from it.
      for (const table of text.matchAll(/const \w+_ICONS = \{([^}]*)\}/g)) for (const m of table[1].matchAll(/: "(\w+)"/g)) used.add(m[1]);
    }
  }
  assert.ok(used.size >= 8, [...used].join(","));
  for (const name of used) assert.ok(Object.hasOwn(ICONS, name), name);
});

test("the slider finishes only past four fifths of its track", () => {
  assert.equal(slideDone(0, 200), false);
  assert.equal(slideDone(159, 200), false);
  assert.equal(slideDone(160, 200), true);
  assert.equal(slideDone(200, 200), true);
  assert.equal(slideDone(10, 0), false);
});

test("every look and feel label exists in English, Portuguese and Chinese, with no dash, 您 and O Lifeline", () => {
  for (const code of ["pt", "zh"]) assert.deepEqual(Object.keys(LOOK_STRINGS[code]).sort(), [...KEYS].sort(), code);
  for (const code of ["en", "pt", "zh"]) {
    for (const key of KEYS) {
      assert.notEqual(STRINGS[code][key].trim(), "", `${key} in ${code}`);
      assert.doesNotMatch(STRINGS[code][key], /[‒-―]| - |--/, `${key} in ${code}`);
    }
  }
  for (const key of KEYS) assert.doesNotMatch(STRINGS.zh[key], /你/, key);
  for (const key of KEYS) assert.doesNotMatch(STRINGS.pt[key], /(^|[.!?]\s)Lifeline/, key);
  const readme = read("../../README.md");
  const section = readme.slice(readme.indexOf("## Waiting for a native speaker"));
  for (const code of ["pt", "zh"]) for (const key of KEYS) assert.ok(section.includes(STRINGS[code][key]), `${key} in ${code} in README`);
});
