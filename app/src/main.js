import { apiBase, USER_ID } from "./config.js";
import { makeApi } from "./api.js";
import { el, relabel } from "./dom.js";
import { t } from "./i18n.js";
import { applyLanguage, languagesFromHealth } from "./languages.js";

const VIEWS = {};

const state = { lang: "en", languages: [] };
const ctx = {
  api: makeApi(apiBase(location.search)),
  userId: USER_ID,
  lang: () => state.lang,
};

async function loadLanguages() {
  const picker = document.getElementById("lang");
  const banner = document.getElementById("health-error");
  banner.hidden = true;
  let health;
  try {
    health = await ctx.api.health();
  } catch {
    banner.replaceChildren(
      el("span", { "data-i18n": "health_failed" }, t(state.lang, "health_failed")),
      el("button", { type: "button", onclick: loadLanguages, "data-i18n": "retry" }, t(state.lang, "retry")),
    );
    banner.hidden = false;
    return;
  }
  state.languages = languagesFromHealth(health);
  picker.replaceChildren(...state.languages.map((language) => el("option", { value: language.code }, language.name)));
  const keep = state.languages.find((language) => language.code === state.lang) ?? state.languages[0];
  if (keep) choose(keep.code);
  picker.disabled = state.languages.length === 0;
}

function choose(code) {
  const language = state.languages.find((item) => item.code === code);
  if (!language) return;
  state.lang = language.code;
  document.getElementById("lang").value = language.code;
  applyLanguage(document, language);
  relabel(document, language.code);
}

function showTab(name) {
  for (const tab of document.querySelectorAll('[role="tab"]')) {
    const on = tab.id === `tab-${name}`;
    tab.setAttribute("aria-selected", String(on));
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !on;
  }
  VIEWS[name]?.shown?.();
}

document.getElementById("lang").addEventListener("change", (event) => choose(event.target.value));
for (const name of ["chat", "rescue", "ledger"]) {
  document.getElementById(`tab-${name}`).addEventListener("click", () => showTab(name));
}
loadLanguages();
