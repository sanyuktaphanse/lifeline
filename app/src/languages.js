// The languages Lifeline replies in come only from GET /health. This file holds no language list of its own.
import { STRINGS } from "./i18n.js";

export function languagesFromHealth(health) {
  const languages = health && typeof health.languages === "object" && health.languages !== null ? health.languages : {};
  return Object.entries(languages).map(([code, meta]) => ({
    code,
    name: meta && typeof meta.name === "string" && meta.name ? meta.name : code,
    direction: meta && meta.direction === "rtl" ? "rtl" : "ltr",
  }));
}

// The app's own labels (buttons, headings) exist for some languages only. Lifeline's replies are always in the
// chosen language; only the labels around them fall back to English.
export function uiLang(code) {
  return Object.hasOwn(STRINGS, code) ? code : "en";
}

export function applyLanguage(doc, language) {
  doc.documentElement.lang = language.code;
  doc.documentElement.dir = language.direction;
}
