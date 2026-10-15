import { apiBase, USER_ID } from "./config.js";
import { makeApi } from "./api.js";
import { el, relabel } from "./dom.js";
import { t } from "./i18n.js";
import { applyLanguage, languagesFromHealth } from "./languages.js";
import { chatView } from "./views/chat.js";
import { rescueView } from "./views/rescue.js";
import { ledgerView } from "./views/ledger.js";
import { guideView } from "./views/guide.js";
import { welcomeView } from "./views/welcome.js";
import { onboardingView } from "./views/onboarding.js";
import { meView } from "./views/me.js";
import { logo } from "./logo.js";
import { planOnFile } from "./onboarding.js";

const VIEWS = {};

const state = { lang: "en", languages: [] };
const ctx = {
  // What the onboarding gave, in page memory only: never sent and never stored, so a reload starts again.
  profile: { trip: null },
  api: makeApi(apiBase(location.search)),
  userId: USER_ID,
  lang: () => state.lang,
  // The plan the server holds: the sample plan with each update GET /ledger records. A read; nothing is written.
  loadPlan: async () => planOnFile(await ctx.api.ledger(USER_ID)),
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
  for (const view of Object.values(VIEWS)) view.relang?.();
  ctx.refreshGreeting?.();
}

// The tab the student was on, so Close on Me goes back to it.
let currentTab = "chat";

// Hides every screen: the welcome, the onboarding, Me, the tabs and their panels.
function hideAll() {
  for (const id of ["view-welcome", "view-onboarding", "view-me"]) document.getElementById(id).hidden = true;
  document.querySelector(".tabs").hidden = true;
  for (const panel of document.querySelectorAll('[role="tabpanel"]')) panel.hidden = true;
}

function showTab(name) {
  currentTab = name;
  hideAll();
  ctx.refreshGreeting?.();
  document.querySelector(".tabs").hidden = false;
  for (const tab of document.querySelectorAll('[role="tab"]')) {
    const on = tab.id === `tab-${name}`;
    tab.setAttribute("aria-selected", String(on));
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !on;
  }
  VIEWS[name]?.shown?.();
}

// The welcome takes the place of the tabs until the student continues. ?welcome=off skips it, for the tests.
function showWelcome() {
  hideAll();
  document.getElementById("view-welcome").hidden = false;
  VIEWS.welcome.shown();
}

document.getElementById("lang").addEventListener("change", (event) => choose(event.target.value));
for (const name of ["chat", "rescue", "ledger", "guide"]) {
  document.getElementById(`tab-${name}`).addEventListener("click", () => showTab(name));
}
// The onboarding after the welcome, and again from Me with "trip" or "plan" to change one part.
function showOnboarding(mode) {
  hideAll();
  document.getElementById("view-onboarding").hidden = false;
  VIEWS.onboarding.start(mode);
}

function showMe() {
  hideAll();
  document.getElementById("view-me").hidden = false;
  VIEWS.me.shown();
}

document.getElementById("open-welcome").addEventListener("click", showWelcome);
document.getElementById("open-me").addEventListener("click", showMe);
document.getElementById("brand").replaceChildren(logo(24));
chatView(ctx, document.getElementById("view-chat"));
rescueView(ctx, document.getElementById("view-rescue"));
VIEWS.ledger = ledgerView(ctx, document.getElementById("view-ledger"));
VIEWS.guide = guideView(ctx, document.getElementById("view-guide"), (words) => {
  showTab("chat");
  ctx.fillMessage(words);
});
VIEWS.welcome = welcomeView(ctx, document.getElementById("view-welcome"), () => showOnboarding("all"));
VIEWS.onboarding = onboardingView(ctx, document.getElementById("view-onboarding"), (next, words) => {
  if (next === "me") return showMe();
  showTab("chat");
  // The plan message goes in the message box for the student to read and send; it is never sent for them.
  if (words) ctx.fillMessage(words);
});
VIEWS.me = meView(ctx, document.getElementById("view-me"), { onChange: showOnboarding, onClose: () => showTab(currentTab) });
if (new URLSearchParams(location.search).get("welcome") === "off") showTab("chat");
else showWelcome();
loadLanguages();
