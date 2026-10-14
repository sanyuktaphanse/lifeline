// Lifeline mockup, phone first. Talks to the real Lifeline API that `make dev` starts (docs/api.md).
// Rules kept from docs/api.md and app/: server text is only ever set as text, never as HTML; a confirmation token
// lives in memory inside its card and is sent back once; pasted text goes in `pasted_text`, never in `text`; the
// rescue takes only typed words and the identity answer is never stored. Nothing is kept in browser storage.

import { sample } from "./sample.js";
import { LANGS, getLang, setLang, t } from "./i18n.js";
import { icon } from "./icons.js";

const API = "http://127.0.0.1:8000";
const USER = "student_001"; // fixture: the demo student, fixtures/demo_user.yaml. There is no sign in yet.
// The Lifeline logo's line, as on a heart monitor.
const PULSE = "M1 12h12l4-9 6 18 5-14 3 5h16";

// When no API answers at all, as on a hosted preview, the screens fill with labelled sample data instead.
let usingSample = false;
function paintPill() {
  const pill = document.querySelector(".demo-pill");
  if (!pill) return;
  pill.textContent = usingSample ? t("preview") : t("demo");
  pill.title = usingSample ? t("previewTitle") : "";
}

// ---------- tiny helpers ----------
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid instanceof Node ? kid : String(kid));
  return el;
}
let noAi = false;
async function call(method, path, body) {
  // With no AI key on this computer, every call after the first answers from the labelled samples, so a sample
  // payment never meets the real API.
  if (noAi) { const fake = sample(method, path, body); if (fake !== null) return structuredClone(fake); }
  let res;
  try {
    res = await fetch(API + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  } catch {
    const fake = sample(method, path, body);
    if (fake !== null) { if (!usingSample) { usingSample = true; paintPill(); } return structuredClone(fake); }
    throw { status: 0, detail: t("serverDown") };
  }
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok && (res.status === 503 || /API_KEY/.test(String(data?.detail ?? ""))) && sample(method, path, body) !== null) {
    noAi = true; usingSample = true; paintPill(); return structuredClone(sample(method, path, body));
  }
  if (!res.ok) throw { status: res.status, detail: data?.detail ?? res.statusText };
  return data;
}
const errorText = (e) => (typeof e?.detail === "string" ? e.detail : e?.detail?.reasons?.join(" ") || t("wentWrong"));
const locale = () => ({ en: "en-SG", pt: "pt-BR", zh: "zh-CN" })[getLang()];
const money = (amount, cur) => { const n = Number(amount); const d = Number.isInteger(n) ? 0 : 2; return `${n.toLocaleString(locale(), { minimumFractionDigits: d, maximumFractionDigits: 2 })} ${cur ?? ""}`.trim(); };
const when = (iso) => new Date(iso).toLocaleString(locale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const days = (iso) => Math.round((new Date(iso).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400e3);
const relDay = (iso) => new Intl.RelativeTimeFormat(locale(), { numeric: "auto" }).format(days(iso), "day");
// Route names as a student knows them. sim_pix is the simulated Pix rail (rails/sim/); bank_wire is a quoted bank transfer.
const RAILS = { wise: "Wise", revolut: "Revolut", sim_pix: "Pix", pix: "Pix", bank_wire: "Bank transfer" };
const rail = (r) => RAILS[r] ?? nice(r);
const nice = (s) => String(s ?? "").replace(/_/g, " ");
const tag = (label) => h("span", { class: "tag" }, label);
const drawTrace = (el) => { el.innerHTML = `<svg viewBox="0 0 48 24" aria-hidden="true"><path class="trace-base" d="${PULSE}"/><path class="trace" pathLength="100" d="${PULSE}"/></svg>`; }; // a fixed drawing, never server text

// ---------- navigation and language ----------
const view = document.getElementById("view");
const tabs = [...document.querySelectorAll(".tabs button")];
const screens = { welcome, setup, plan, hello, soon, home, chat, sos, activity, help, roadmap, lost, me };
const FULL = new Set(["welcome", "setup", "plan", "hello", "soon", "lost"]);
let currentScreen = "welcome";
function go(name, arg) {
  currentScreen = name;
  tabs.forEach((b) => (b.dataset.tab === name ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  view.replaceChildren();
  view.classList.remove("chatting");
  document.body.classList.toggle("signin", FULL.has(name));
  view.dataset.screen = name;
  screens[name](arg);
  window.scrollTo(0, 0);
  view.focus({ preventScroll: true });
}
tabs.forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));
const TAB_ICONS = { home: "home", chat: "chat", sos: "buoy", activity: "history", help: "help" };
tabs.forEach((b) => b.querySelector(".ic").replaceChildren(icon(TAB_ICONS[b.dataset.tab])));
function paintChrome() {
  const names = { home: "tabHome", chat: "tabChat", sos: "tabSos", activity: "tabActivity", help: "tabHelp" };
  tabs.forEach((b) => { const label = t(names[b.dataset.tab]); b.setAttribute("aria-label", label); b.lastElementChild.textContent = label; });
  paintPill();
  document.querySelector(".me-btn")?.setAttribute("aria-label", t("me"));
  document.querySelectorAll(".lang").forEach((sel) => { sel.value = getLang(); sel.setAttribute("aria-label", t("language")); });
}
function langPicker(extraClass = "") {
  const sel = h("select", { class: `lang ${extraClass}`, "aria-label": t("language"), onchange: (e) => { setLang(e.target.value); paintChrome(); go(currentScreen); } },
    LANGS.map(([code, short, name]) => h("option", { value: code, title: name }, short)));
  sel.value = getLang();
  return sel;
}
const meBtn = h("button", { class: "me-btn", "aria-label": t("me"), onclick: () => go("me") }, icon("user"));
document.querySelector(".top").append(langPicker(), meBtn);

// ---------- Welcome: a line at the top, the heartbeat in the middle, one action at the bottom ----------
// The API has no sign in (docs/api.md, "Security"; self assessment, open item 37), so only "Try the demo" works and
// the sign in icons say coming soon. Nothing is remembered: a reload shows this again.
function welcome() {
  const icon = (label, src) => h("button", { class: "sso-dot", "aria-label": `${label}, ${t("soon")}`, onclick: () => go("soon", label) }, h("img", { src, alt: "" }));
  const [a, b, c] = t("wTitle");
  const orb = h("div", { class: "orb", role: "img", "aria-label": t("orb") });
  drawTrace(orb);
  view.append(
    langPicker("float"),
    h("div", { class: "w-top" }, h("h1", {}, a, h("em", {}, b), c), h("p", { class: "w-sub" }, t("wSub"))),
    h("div", { class: "w-mid" }, h("span", { class: "aura", "aria-hidden": "true" }), orb),
    h("div", { class: "w-bottom" },
      h("button", { class: "btn", onclick: () => go("setup") }, t("tryDemo")),
      h("div", { class: "sso-row" }, icon("Email", "icons/mail.png"), icon("Apple", "icons/apple.png"), icon("Google", "icons/google.png")),
      h("p", { class: "fine" }, t("signinSoon"))),
  );
}

// ---------- Setup: three questions about the trip ----------
// Kept only in memory while the page is open. The backend runs one demo student, so the answers change tips and
// suggestions, never payments or balances; the screen says so.
let trip = null;
function setup(next = "hello") {
  const pickd = { home: trip?.home ?? null, study: trip?.study ?? null, purpose: trip?.purpose ?? null };
  const cont = h("button", { class: "btn", onclick: () => { trip = { ...pickd }; go(next === "hello" ? "plan" : next, next === "hello" ? { i: 0 } : undefined); } }, t("cont"));
  const group = (key, q, why, options) => {
    const row = h("div", { class: "chips wrap pick" });
    const paint = () => { row.replaceChildren(...Object.entries(options).map(([k, label]) => h("button", { class: "chip", "aria-pressed": String(pickd[key] === k), onclick: () => { pickd[key] = k; paint(); ready(); } }, label))); };
    paint();
    return h("section", { class: "q" }, h("h2", {}, q), why ? h("p", { class: "muted small" }, why) : "", row);
  };
  const ready = () => { cont.disabled = !(pickd.home && pickd.study && pickd.purpose); };
  const country = (key, q, why, ready) => h("section", { class: "q" }, h("h2", {}, q), h("p", { class: "muted small" }, why),
    countryPicker(pickd[key], ready, (code) => { pickd[key] = code; readyBtn(); }));
  const readyBtn = () => ready();
  view.append(
    h("div", { class: "hello" }, h("h1", {}, t("setupTitle")), h("p", {}, t("setupSub"))),
    h("section", { class: "card" },
      country("home", t("qHome"), t("qHomeWhy"), HOME_READY),
      country("study", t("qStudy"), t("qStudyWhy"), STUDY_READY),
      group("purpose", t("qWhat"), "", t("purposesTrip"))),
    h("p", { class: "muted small", style: "text-align:center;margin:0 8px 12px" }, t("setupNote")),
    cont, h("button", { class: "link center", onclick: () => { trip = null; go(next); } }, t("skip")));
  ready();
}
// ---------- Plan: the safety net, asked one question at a time ----------
// Kept only in memory. The safety answer itself is never kept, only that one was given. The backend's rescue still
// runs the demo student's plan in fixtures/demo_user.yaml, and the question step says so.
let mine = null;
const PLAN_STEPS = 5;
function plan(arg = {}) {
  const i = arg.i ?? 0, back = arg.back ?? null;
  const draft = mine ? { ...mine } : { card: null, backup: undefined, question: null, answered: false, contactName: "", channel: null, emergency: null };
  const cardKeys = trip?.study === "sg" ? ["wise", "revolut", "youtrip", "dbs", "ocbc", "uob", "home", "unsure"] : ["wise", "revolut", "home", "unsure"];
  const cont = h("button", { class: "btn" }, t("cont"));
  const extra = h("div", {});
  const chips = (options, value, onPick) => {
    const row = h("div", { class: "chips wrap pick" });
    const paint = (v) => row.replaceChildren(...Object.entries(options).map(([k, label]) => h("button", { class: "chip", "aria-pressed": String(v === k), onclick: () => { onPick(k); paint(k); } }, label)));
    paint(value); return row;
  };
  const card = t("cards");
  let body, after = "", ok = () => true;
  if (i === 0) {
    // Always shown, in its own card under the question, so a student who has never heard of these cards can choose.
    after = h("section", { class: "card info-card" }, h("h3", {}, icon("sparkle"), h("span", {}, t("unsureTitle"))),
      h("ul", {}, h("li", {}, t("unsureTravel")), trip?.study === "sg" ? h("li", {}, t("unsureLocal")) : "", h("li", {}, t("unsureHome"))), h("p", { class: "muted small" }, t("unsureNote")));
    body = [h("h2", {}, t("qCard")), h("p", { class: "muted small" }, t("qCardWhy")),
      chips(Object.fromEntries(cardKeys.map((k) => [k, card[k]])), draft.card, (k) => { draft.card = k; ready(); })];
    ok = () => !!draft.card;
  } else if (i === 1) {
    const which = h("div", {});
    const paintWhich = () => which.replaceChildren(draft.backup === null ? h("p", { class: "note" }, t("backupNoNote"), draft.card === "wise" && trip?.study === "sg" ? " " + t("wiseWait") : "")
      : draft.backup !== undefined ? h("div", {}, h("h3", {}, t("qBackupWhich")), chips(Object.fromEntries(cardKeys.filter((k) => k !== draft.card && k !== "unsure").map((k) => [k, card[k]])), draft.backup === "yes" ? null : draft.backup, (k) => { draft.backup = k; ready(); })) : "");
    body = [h("h2", {}, t("qBackup")), h("p", { class: "muted small" }, t("qBackupWhy")),
      chips({ yes: t("yes"), no: t("noJustOne") }, draft.backup === undefined ? null : draft.backup === null ? "no" : "yes", (k) => { draft.backup = k === "no" ? null : "yes"; paintWhich(); ready(); }), which];
    paintWhich(); ok = () => draft.backup === null || (draft.backup !== undefined && draft.backup !== "yes");
  } else if (i === 2) {
    const qs = t("questions");
    const sel = h("select", { class: "field", "aria-label": t("qQuestion"), onchange: (e) => { draft.question = Number(e.target.value); ready(); } },
      h("option", { value: "", disabled: true, selected: draft.question === null }, "…"), qs.map((q, n) => h("option", { value: String(n), selected: draft.question === n }, q)));
    const ans = typed(h("input", { class: "field", type: "password", autocomplete: "off", placeholder: t("yourAnswer"), "aria-label": t("yourAnswer"), oninput: (e) => { draft.answered = e.target.value.trim().length > 0; ready(); } }));
    body = [h("h2", {}, t("qQuestion")), h("p", { class: "muted small" }, t("qQuestionWhy")), sel, ans, h("p", { class: "note" }, t("answerNote"))];
    ok = () => draft.question !== null && (draft.answered || mine?.answered);
  } else if (i === 3) {
    const name = h("input", { class: "field", type: "text", autocomplete: "off", placeholder: t("contactName"), "aria-label": t("contactName"), value: draft.contactName, oninput: (e) => { draft.contactName = e.target.value; ready(); } });
    body = [h("h2", {}, t("qContact")), h("p", { class: "muted small" }, t("qContactWhy")), name,
      chips(t("channels"), draft.channel, (k) => { draft.channel = k; ready(); }),
      h("button", { class: "link", onclick: () => { draft.contactName = ""; draft.channel = null; mine = draft; next(); } }, t("noOne"))];
    ok = () => draft.contactName.trim() && draft.channel;
  } else {
    body = [h("h2", {}, t("qEmergency")), h("p", { class: "muted small" }, t("qEmergencyWhy")),
      chips({ 100: money(100, "SGD"), 200: money(200, "SGD"), 300: money(300, "SGD"), 0: t("none") }, draft.emergency === null ? null : String(draft.emergency), (k) => { draft.emergency = Number(k); ready(); })];
    ok = () => draft.emergency !== null;
  }
  function ready() { cont.disabled = !ok(); }
  function next() { mine = draft; i + 1 < PLAN_STEPS ? go("plan", { i: i + 1, back }) : go(back || "hello"); }
  cont.addEventListener("click", next);
  view.append(
    h("div", { class: "steps plan-steps", "aria-hidden": "true" }, Array.from({ length: PLAN_STEPS }, (_, n) => h("span", { class: n <= i ? "on" : "" }))),
    h("p", { class: "muted small plan-count" }, t("planStep", { n: i + 1, total: PLAN_STEPS })),
    h("section", { class: "card q-card" }, body),
    after,
    cont,
    h("div", { class: "plan-links" },
      h("button", { class: "link", onclick: () => (i ? go("plan", { i: i - 1, back }) : go(back || "setup")) }, t("back")),
      back ? "" : h("button", { class: "link", onclick: () => { mine = null; go("hello"); } }, t("skip"))));
  ready();
}
// The safety net as the student set it, or the demo student's when they skipped.
function netItems() {
  if (!mine) return t("plan").map(([, what, sub], n) => [["card", "buoy", "lock", "cash"][n], what, sub]);
  const card = t("cards");
  return [
    ["card", t("sMain"), mine.card && mine.card !== "unsure" ? card[mine.card] : t("notChosen")],
    ["buoy", t("sBackup"), mine.backup ? card[mine.backup] : t("noneYet")],
    ["lock", t("sQuestion"), mine.question !== null ? `${t("questions")[mine.question]} · ${t("answerSet")}` : t("noneYet")],
    ["family", t("sContact"), mine.contactName ? t("contactVia", { name: mine.contactName, channel: t("channels")[mine.channel] }) : t("noneYet")],
    ["cash", t("sEmergency"), mine.emergency ? t("upTo", { amount: money(mine.emergency, "SGD") }) : t("off")],
  ];
}

// Every country, named in the page language by the browser. Only those with checked rules in rails/knowledge can be
// picked today: China, Brazil and India as home, Singapore as the place of study. The rest show as coming soon.
const COUNTRIES = "AF AX AL DZ AS AD AO AI AG AR AM AW AU AT AZ BS BH BD BB BY BE BZ BJ BM BT BO BA BW BR VG BN BG BF BI CV KH CM CA KY CF TD CL CN CO KM CG CD CK CR CI HR CU CW CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FK FO FJ FI FR GF PF GA GM GE DE GH GI GR GL GD GP GU GT GG GN GW GY HT HN HK HU IS IN ID IR IQ IE IM IL IT JM JP JE JO KZ KE KI XK KW KG LA LV LB LS LR LY LI LT LU MO MG MW MY MV ML MT MH MQ MR MU YT MX FM MD MC MN ME MS MA MZ MM NA NR NP NL NC NZ NI NE NG NU KP MK MP NO OM PK PW PS PA PG PY PE PH PL PT PR QA RE RO RU RW WS SM ST SA SN RS SC SL SG SX SK SI SB SO ZA KR SS ES LK SD SR SE CH SY TW TJ TZ TH TL TG TO TT TN TR TM TC TV UG UA AE GB US UY UZ VU VA VE VN WF EH YE ZM ZW".split(" ");
const HOME_READY = ["CN", "BR", "IN"], STUDY_READY = ["SG"];
const flag = (code) => String.fromCodePoint(...[...code].map((ch) => 0x1F1E6 + ch.charCodeAt(0) - 65));
const place = (k) => { try { return new Intl.DisplayNames([locale()], { type: "region" }).of(k.toUpperCase()); } catch { return k.toUpperCase(); } };
function countryPicker(current, ready, onPick) {
  let chosen = current ? current.toUpperCase() : null;
  const label = h("span", { class: "cp-label" });
  const btn = h("button", { class: "cp-btn", type: "button", "aria-haspopup": "listbox", "aria-expanded": "false" }, label, icon("chev"));
  const search = h("input", { class: "cp-search", type: "search", placeholder: t("searchCountry"), "aria-label": t("searchCountry"), autocomplete: "off" });
  const list = h("div", { class: "cp-list", role: "listbox" });
  const panel = h("div", { class: "cp-panel", hidden: true }, search, list);
  const wrap = h("div", { class: "cp" }, btn, panel);
  const paintBtn = () => label.replaceChildren(chosen ? h("span", {}, flag(chosen), " ", place(chosen)) : h("span", { class: "muted" }, t("chooseCountry")));
  const sorted = () => COUNTRIES.map((c) => ({ c, name: place(c) })).sort((a, b) => a.name.localeCompare(b.name, locale()));
  function paintList() {
    const q = search.value.trim().toLowerCase();
    const all = sorted().filter((x) => !q || x.name.toLowerCase().includes(q) || x.c.toLowerCase() === q);
    const open = all.filter((x) => ready.includes(x.c)), soon = all.filter((x) => !ready.includes(x.c));
    const item = (x, ok) => h("button", { type: "button", class: `cp-item${ok ? "" : " cp-soon"}${x.c === chosen ? " on" : ""}`, role: "option", "aria-selected": String(x.c === chosen), "aria-disabled": ok ? "false" : "true", disabled: !ok,
      onclick: () => { chosen = x.c; onPick(x.c.toLowerCase()); paintBtn(); close(); btn.focus(); } }, h("span", { class: "cp-flag", "aria-hidden": "true" }, flag(x.c)), h("span", {}, x.name));
    list.replaceChildren(
      ...(open.length ? [h("p", { class: "cp-h" }, t("availableNow")), ...open.map((x) => item(x, true))] : []),
      ...(soon.length ? [h("p", { class: "cp-h" }, t("comingSoonH")), ...soon.map((x) => item(x, false))] : []),
      ...(all.length ? [] : [h("p", { class: "muted small cp-none" }, t("noMatch"))]));
  }
  const openP = () => { panel.hidden = false; btn.setAttribute("aria-expanded", "true"); search.value = ""; paintList(); search.focus(); };
  const close = () => { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", () => (panel.hidden ? openP() : close()));
  search.addEventListener("input", paintList);
  wrap.addEventListener("keydown", (e) => { if (e.key === "Escape") { close(); btn.focus(); } });
  document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) close(); });
  paintBtn();
  return wrap;
}
const tripLine = () => trip && t("tripLine", { purpose: t("purposesTrip")[trip.purpose], home: place(trip.home), study: place(trip.study) });
// The sourced tips for the route: the home country's, the study country's, then one for everyone.
function routeTips(limit = Infinity) {
  const all = t("tips");
  const list = [...(all[trip?.home] || []), ...(all[trip?.study] || []), ...all.all].slice(0, limit);
  const known = trip && (all[trip.home] || all[trip.study]); // every pickable country has tips, so this is a guard
  return h("section", { class: "card tips" }, h("h2", {}, t("goodToKnow")),
    trip && !known ? h("p", { class: "muted small" }, t("noRules")) : "",
    h("ul", { class: "list" }, list.map(([, text, src]) => h("li", {}, h("span", { class: "emoji ib" }, icon("sparkle")), h("div", {}, h("div", {}, text), h("div", { class: "muted small" }, t("source", { s: src })))))));
}

// After Try the demo: the demo plan in fixtures/demo_user.yaml as docs/api.md, "Rescue", states it. Nothing is asked.
function hello() {
  view.append(
    h("div", { class: "hello" }, (() => { const o = h("div", { class: "orb mini-orb", "aria-hidden": "true" }); drawTrace(o); return o; })(), h("h1", {}, t("helloTitle")), trip ? h("p", { class: "trip-pill" }, tripLine()) : "", h("p", {}, mine ? t("mineSub") : trip ? t("helloSubTrip") : t("helloSub"))),
    h("section", { class: "card" }, h("h2", {}, t("safetyNet")), h("p", { class: "muted small" }, mine ? t("netIntroMine") : t("safetyIntro")),
      h("ul", { class: "list" }, netItems().map(([ic, what, sub]) => h("li", {}, h("span", { class: "emoji ib" }, icon(ic)), h("div", {}, h("div", { class: "what" }, what), h("div", { class: "muted small" }, sub)))))),
    trip ? routeTips(3) : "",
    mine ? "" : h("p", { class: "muted small", style: "text-align:center" }, t("ownPlanSoon")),
    slider(t("slideStart"), t("getStarted"), () => go("home")),
  );
}

// Slide to start. Dragging the knob past most of the track starts; Enter or Space on the knob does too, for keyboards.
function slider(label, a11y, done) {
  const fill = h("span", { class: "fill", "aria-hidden": "true" });
  const knob = h("button", { class: "knob", "aria-label": a11y }, "›");
  const text = h("span", { class: "slider-label", "aria-hidden": "true" }, label);
  const track = h("div", { class: "slider" }, fill, text, knob);
  let startX = null, x = 0, moved = false;
  const max = () => track.clientWidth - knob.offsetWidth - 12;
  const paint = () => { knob.style.transform = `translateX(${x}px)`; fill.style.width = `${x + knob.offsetWidth + 6}px`; text.style.opacity = String(1 - x / max()); };
  knob.addEventListener("pointerdown", (e) => { startX = e.clientX - x; moved = false; knob.setPointerCapture(e.pointerId); track.classList.add("dragging"); });
  knob.addEventListener("pointermove", (e) => { if (startX === null) return; x = Math.max(0, Math.min(max(), e.clientX - startX)); if (x > 4) moved = true; paint(); });
  const release = () => {
    if (startX === null) return; startX = null; track.classList.remove("dragging");
    if (x > max() * 0.8) { x = max(); paint(); setTimeout(done, 180); } else { x = 0; paint(); if (!moved) { track.classList.remove("hint"); void track.offsetWidth; track.classList.add("hint"); } }
  };
  knob.addEventListener("pointerup", release); knob.addEventListener("pointercancel", release);
  knob.addEventListener("click", (e) => { if (e.detail === 0) done(); }); // a keyboard press, not a tap
  return track;
}

// ---------- Coming soon: where the sign in icons lead ----------
function soon(name) {
  const orb = h("div", { class: "orb mini-orb", "aria-hidden": "true" }); drawTrace(orb);
  view.append(h("div", { class: "soon" }, orb, h("h1", {}, t("soonTitle")), h("p", {}, t("soonBody", { name: name || "" })),
    h("button", { class: "btn", onclick: () => go("setup") }, t("tryDemo")),
    h("button", { class: "link center", onclick: () => go("welcome") }, t("soonBack"))));
}

// ---------- Home: a calm assistant home, four live cards and the message box ----------
async function home() {
  const orb = h("div", { class: "orb mini-orb", "aria-hidden": "true" }); drawTrace(orb);
  const rentSub = h("span", { class: "sub" }, t("cRentSub"));
  const badge = h("span", { class: "badge" }, t("checking"));
  const count = h("span", { class: "count", hidden: true });
  const card = (cls, ic, title, sub, onclick) => h("button", { class: `tile ${cls}`, onclick }, h("span", { class: "ico" }, icon(ic)), h("span", { class: "ttl" }, title), sub);
  const balance = balanceCard();
  const remindList = h("ul", { class: "list" }, h("li", {}, h("span", { class: "muted small" }, t("nothingScheduled"))));
  const remindBox = h("section", { class: "card reminders", hidden: true }, h("h2", {}, t("comingUp")), remindList,
    h("button", { class: "link", onclick: () => go("chat", { prompt: t("more")[1] }) }, t("setReminder")));
  const [q0, q1, q2, q3] = t("quick");
  const ask = h("textarea", { class: "msg", rows: "2", placeholder: t("askPh"), "aria-label": t("yourMessage") });
  const sendIt = () => { const v = ask.value.trim(); if (v) go("chat", { prompt: v, send: true }); else ask.focus(); };
  ask.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendIt(); } });
  // A paste here is someone else's words, so it opens Chat with the message attached rather than as the student's own.
  ask.addEventListener("paste", (e) => { const v = e.clipboardData?.getData("text") ?? ""; if (!v) return; e.preventDefault(); go("chat", { prompt: ask.value, pasted: v }); });
  view.append(
    h("div", { class: "home-hero" },
      h("button", { class: "bell", "aria-label": t("reminders"), "aria-expanded": "false", onclick: (ev) => { const open = remindBox.hidden; remindBox.hidden = !open; ev.currentTarget.setAttribute("aria-expanded", String(open)); } }, icon("bell"), count), orb, h("p", { class: "muted" }, !trip ? t("homeHello") : trip.study === "other" ? t("homeHelloAbroad") : t("homeHelloIn", { place: place(trip.study) })),
      h("h1", {}, t("homeHead")[0], h("br"), h("span", { class: "soft" }, t("homeHead")[1]))),
    remindBox,
    balance,
    h("div", { class: "tiles" },
      card("rent", "home", t("cRent"), rentSub, () => go("chat", { ...q0, send: true })),
      card("lost", "buoy", t("cLost"), h("span", { class: "sub" }, t("cLostSub")), () => go("sos")),
      card("home", "inbound", t("cHome"), h("span", { class: "sub" }, trip && trip.home !== "other" ? t("fromFamily", { home: place(trip.home) }) : t("cHomeSub")), () => go("chat", { ...q1, send: true })),
      card("scam", "shield", t("cScam"), h("span", { class: "sub" }, t("cScamSub")), () => go("chat", q2))),
    h("div", { class: "glow-box" }, ask,
      h("div", { class: "glow-actions" }, h("button", { class: "iconbtn", "aria-label": t("attach"), onclick: () => go("chat", { prompt: ask.value, attach: true }) }, icon("clip")),
        h("span", { style: "flex:1" }), h("button", { class: "iconbtn send", "aria-label": t("send"), onclick: sendIt }, icon("send")))),
    h("div", { class: "home-foot" }, h("button", { class: "link", onclick: () => go("activity") }, badge), h("button", { class: "link", onclick: () => go("roadmap") }, t("whatsNext"))),
  );
  try {
    const r = await call("GET", `/reminders/${USER}`);
    const items = [...(r.due || []), ...(r.upcoming || [])];
    if (items.length) rentSub.textContent = t("dueIn", { text: items[0].text, when: relDay(items[0].due) });
    if (items.length) remindList.replaceChildren(...items.map((it) => h("li", {}, h("span", { class: "a-ic" }, icon("clock")), h("div", { class: "a-main" }, h("div", { class: "what" }, it.text), h("div", { class: "muted small" }, relDay(it.due))))));
    if ((r.due || []).length) { count.textContent = String(r.due.length); count.hidden = false; count.setAttribute("aria-label", t("due", { n: r.due.length })); }
  } catch { /* the card keeps its plain subtitle */ }
  try { setBadge(badge, await call("GET", `/ledger/${USER}/verify`)); } catch { badge.remove(); }
}

// The balance, from the demo fixture. The API has no balance endpoint yet, so when it does not answer the card shows the
// fixture figures labelled Sample. A tap on the eye hides the figures, for checking the app in public.
function balanceCard() {
  let hidden = false;
  const figs = h("div", { class: "bal-figs" });
  const label = h("span", { class: "muted small" }, t("balance"));
  const eye = h("button", { class: "eye", "aria-label": t("hideBal"), onclick: () => { hidden = !hidden; paint(); } });
  let data = null, isSample = false;
  function paint() {
    eye.replaceChildren(icon(hidden ? "eyeOff" : "eye")); eye.setAttribute("aria-label", hidden ? t("showBal") : t("hideBal"));
    figs.replaceChildren(...(data ? Object.entries(data).map(([cur, amt], i) => h("span", { class: i ? "bal-sub" : "bal-main" }, hidden ? `•••• ${cur}` : money(amt, cur))) : []));
  }
  const box = h("section", { class: "card balance" }, h("div", { class: "bal-head" }, h("span", { class: "bal-ic" }, icon("wallet")), label, h("span", { style: "flex:1" }), eye), figs,
    h("p", { class: "bal-where" }, icon("lock"), h("span", {}, t("balWhere"))));
  (async () => {
    try { data = await call("GET", `/balances/${USER}`); } catch { data = sample("GET", `/balances/${USER}`); isSample = true; }
    if (isSample || usingSample) label.after(tag(t("sample")));
    paint();
  })();
  paint();
  return box;
}

// ---------- Chat ----------
const thread = []; // what the chat shows, kept only while the page is open
function chat(seed) {
  const list = h("div", { class: "thread", "aria-live": "polite" });
  const msg = h("textarea", { class: "msg", rows: "1", placeholder: t("message"), "aria-label": t("yourMessage") });
  const pasteBox = h("textarea", { "aria-label": t("received"), placeholder: t("pasteHere") });
  const attached = h("div", { class: "attached", hidden: true },
    h("span", { class: "label" }, t("received")), pasteBox,
    h("button", { class: "link", onclick: () => { pasteBox.value = ""; attached.hidden = true; } }, t("remove")));
  const send = h("button", { class: "iconbtn send", "aria-label": t("send"), onclick: () => submit() }, icon("send"));
  const clip = h("button", { class: "iconbtn", "aria-label": t("attach"), title: t("attach"), onclick: () => { attached.hidden = false; pasteBox.focus(); } }, icon("clip"));
  const QICONS = ["home", "inbound", "shield", "wallet"];
  // A paste into the message box is someone else's words, so it moves to the attached message.
  msg.addEventListener("paste", (ev) => {
    const text = ev.clipboardData?.getData("text") ?? "";
    if (!text) return;
    ev.preventDefault();
    pasteBox.value = (pasteBox.value ? pasteBox.value + "\n" : "") + text;
    attached.hidden = false;
  });
  const chips = h("div", { class: "chips" },
    t("quick").map((q, i) => h("button", { class: "chip top", onclick: () => use(q) }, icon(QICONS[i]), q.label)),
    h("button", { class: "chip", onclick: (ev) => { ev.currentTarget.remove(); t("more").forEach((p) => chips.append(h("button", { class: "chip", onclick: () => use({ prompt: p }) }, p))); } }, t("moreIdeas")));
  function use(q) {
    msg.value = q.prompt || "";
    if (q.pasted) { pasteBox.value = q.pasted; attached.hidden = false; }
    if (q.attach) { attached.hidden = false; pasteBox.focus(); } else msg.focus();
  }

  async function submit() {
    const text = msg.value.trim();
    const pasted = attached.hidden ? "" : pasteBox.value.trim();
    if (!text) { push(h("div", { class: "error" }, pasted ? t("typeOwn") : t("typeFirst"))); return; }
    starters.remove(); chips.hidden = false;
    push(h("div", { class: "bubble me" }, text));
    push(h("div", { class: "stamp" }, new Date().toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" })));
    if (pasted) push(h("div", { class: "bubble quoted" }, h("span", { class: "label" }, t("received")), pasted));
    msg.value = ""; pasteBox.value = ""; attached.hidden = true; send.disabled = true;
    const mini = h("span", { class: "mini", "aria-hidden": "true" });
    drawTrace(mini);
    const typing = h("div", { class: "thinking", role: "status", "aria-label": t("thinking") }, mini, h("span", { class: "dots", "aria-hidden": "true" }, h("i"), h("i"), h("i")));
    list.append(typing);
    try {
      const body = { user_id: USER, text, lang: getLang() };
      if (pasted) body.pasted_text = pasted;
      showReply(await call("POST", "/chat", body));
    } catch (e) {
      push(h("div", { class: "error" }, e.status === 503 || /API_KEY/.test(errorText(e)) ? `${t("noAi")} (${errorText(e)})` : errorText(e)));
    } finally { typing.remove(); send.disabled = false; }
  }
  function push(node) { thread.push(node); list.append(node); node.scrollIntoView({ block: "end", behavior: "smooth" }); }
  function showReply(r) { replyNodes(r, showReply).forEach(push); }

  // An empty chat offers four starting questions in the middle, so the screen is never blank.
  const extra = { cn: { label: t("more")[4], prompt: t("more")[4] }, br: { label: t("more")[3], prompt: t("more")[3] } }[trip?.home];
  const starterList = extra ? [...t("quick"), extra] : t("quick");
  const starters = h("div", { class: "starters" }, h("p", { class: "muted small" }, t("tryAsking")),
    starterList.map((q, i) => h("button", { class: "starter", onclick: () => { use(q); if (!q.attach) submit(); } }, h("span", { class: "s-ic" }, icon(QICONS[i] || "sparkle")), h("span", {}, q.label), icon("arrowUp", "s-go"))));
  view.classList.add("chatting");
  view.append(h("h1", {}, t("chat")), list, h("div", { class: "composer" }, chips, attached, h("div", { class: "line" }, clip, msg, send)));
  list.append(...thread);
  if (thread.length === 0) { list.append(answerNode(t("hello"), false, false), starters); chips.hidden = true; }
  if (seed) { use(seed); if (seed.send) submit(); }
}

// Turns an AgentReply into nodes, in the order docs/api.md "Reading an AgentReply" gives.
function replyNodes(r, onReply, inRescue = false) {
  const answer = (text, isSample) => answerNode(text, isSample, !inRescue);
  const out = [];
  let body = r.text || "";
  for (const s of r.blocked || []) { out.push(h("div", { class: "blocked" }, icon("ban"), h("span", {}, t("blocked"), s))); body = body.replace(s, ""); }
  if (r.turn_summary) body = body.replace(r.turn_summary, "");
  body = body.trim();
  if (body) out.push(answer(body, r.sample));
  if (r.receipt) out.push(receiptCard(r.receipt));
  if (r.freeze) out.push(h("div", { class: "bubble bot" }, t("freeze", { s: nice(r.freeze.status) }), r.freeze.deep_link ? h("a", { href: r.freeze.deep_link, target: "_blank", rel: "noopener" }, t("openCardApp")) : ""));
  if (r.cancel) out.push(h("div", { class: "bubble bot" }, t("cancel", { s: nice(r.cancel.status) }), r.cancel.reason ? `. ${r.cancel.reason}` : ""));
  // In a rescue the step has its own Freeze or Send button, which goes to /rescue/step, so no payment sheet is drawn.
  if (r.confirmation && !inRescue) out.push(paymentSheet(r.confirmation, onReply));
  if (r.turn_summary) out.push(h("div", { class: "summary" }, "✓ ", r.turn_summary));
  return out;
}
function answerNode(text, isSample, copyable = true) {
  const mini = h("span", { class: "mini", "aria-hidden": "true" }); drawTrace(mini);
  const copy = h("button", { class: "chipbtn", onclick: async () => { try { await navigator.clipboard.writeText(text); copy.lastChild.textContent = t("copied"); } catch { /* the text stays selectable */ } } }, icon("copy"), h("span", {}, t("copy")));
  return h("div", { class: "answer" },
    h("div", { class: "who" }, mini, h("span", {}, t("answer")), isSample ? tag(t("sample")) : ""),
    h("p", {}, text), copyable ? h("div", { class: "answer-actions" }, copy) : "");
}
function receiptCard(rc) {
  return h("div", { class: "card sheet" },
    h("h2", { class: "sent-h" }, rc.status === "completed" ? icon("check") : icon("clock"), h("span", {}, rc.status === "completed" ? t("sent") : t("transferStatus", { s: nice(rc.status) }))),
    h("p", { class: "amount" }, money(rc.amount, rc.currency)),
    h("p", { class: "muted" }, t("via", { rail: rail(rc.rail), id: rc.receipt_id }), rc.simulated ? tag(t("simulated")) : ""));
}

// The payment sheet: what moves, to whom, by which route and at what cost, then one clear confirm.
function paymentSheet(c, onReply) {
  const a = c.action || {};
  let token = c.confirmation_token; // in memory only, sent back once
  const sel = c.selected_route;
  const arrive = (hrs) => (Number(hrs) === 0 ? t("instant") : t("hours", { n: hrs }));
  const line = (label, value, extra) => h("div", { class: "sheet-row" }, h("span", { class: "muted" }, label), h("span", {}, value, extra || ""));
  const rows = [];
  if (a.payee_id) rows.push(line(t("to"), t("payees")[a.payee_id] ?? a.payee_id));
  if (a.purpose) rows.push(line(t("forWhat"), t("purposes")[a.purpose] ?? nice(a.purpose)));
  if (sel) {
    const fee = Number(sel.fee || 0), fx = Number(sel.spread_cost || 0);
    rows.push(line(t("viaLabel"), rail(sel.rail), sel.simulated ? tag(t("simulated")) : ""));
    rows.push(line(t("fee"), money(fee, sel.currency_from)));
    if (fx) rows.push(line(t("fx"), money(fx, sel.currency_from)));
    rows.push(line(t("arrives"), arrive(sel.arrival_hours)));
    if (a.amount) rows.push(h("div", { class: "sheet-row total" }, h("span", {}, t("total")), h("span", {}, money(Number(a.amount) + fee + fx, a.currency))));
  }
  const routes = (c.routes || []).map((rt) => {
    const on = sel && rt.rail === sel.rail;
    const off = rt.blocked_reason || rt.limit_ok === false || rt.status === "down";
    return h("div", { class: `route${on ? " sel" : ""}${off ? " off" : ""}` },
      on ? icon("check", "r-tick") : h("span", { class: "r-gap", "aria-hidden": "true" }),
      h("span", { class: "r-main" }, h("span", { class: "r-name" }, rail(rt.rail), rt.simulated ? tag(t("simulated")) : ""),
        h("span", { class: "muted small" }, off ? t("blockedRoute") : t("feeShort", { fee: money(rt.fee, rt.currency_from), t: arrive(rt.arrival_hours) }))));
  });
  const timer = h("span", {});
  const yes = h("button", { class: "btn", onclick: async () => {
    if (!token) return;
    const tk = token; token = null; stop(); yes.disabled = no.disabled = true; yes.textContent = t("sending"); no.hidden = true; timer.hidden = true;
    try { onReply(await call("POST", "/confirm", { user_id: USER, confirmation_token: tk, lang: getLang() })); }
    catch (e) { onReply({ text: errorText(e), blocked: [], turn_summary: null }); }
    yes.textContent = t("confirmed");
  } }, a.type === "transfer" ? t("confirmSend") : t("confirmBtn"));
  const no = h("button", { class: "link", onclick: () => { token = null; stop(); yes.hidden = true; no.disabled = true; no.textContent = t("notSent"); no.classList.add("done"); timer.hidden = true; } }, t("notNow"));
  // A live countdown to the token's expiry, so the student knows how long the confirmation lasts.
  let left = c.expires_in_seconds || 300;
  const tick = () => { timer.textContent = t("expires", { t: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` }); if (left-- <= 0) { stop(); token = null; yes.disabled = true; timer.textContent = t("expired"); } };
  tick();
  const id = setInterval(() => { if (!document.contains(timer)) return stop(); tick(); }, 1000);
  function stop() { clearInterval(id); }
  return h("div", { class: "card sheet" },
    h("div", { class: "sheet-head" }, h("span", { class: "muted small" }, t("review")), h("span", { class: "muted small" }, timer)),
    h("p", { class: "muted" }, t("types")[a.type] ?? nice(a.type)),
    a.amount ? h("p", { class: "amount big" }, money(a.amount, a.currency)) : "",
    rows.length ? h("div", { class: "sheet-rows" }, rows) : "",
    routes.length > 1 ? h("details", { class: "compare" }, h("summary", {}, h("span", {}, t("compare", { n: routes.length })), icon("chev")), h("div", { class: "routes" }, h("p", { class: "muted small route-why" }, t("routeWhy")), routes)) : "",
    h("div", { class: "warn" }, icon("alert"), h("span", {}, t("warnings")[c.warning_key] ?? t("checkFirst"))),
    yes, h("div", { style: "text-align:center" }, no));
}

// ---------- Lost card ----------
const ORDER = ["S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9", "done"];
function sos() {
  const box = h("div", {});
  view.append(h("h1", {}, t("sosTitle")), box);
  start();
  function start() {
    let trigger = "card_lost";
    const lost = h("button", { class: "choice", "aria-pressed": "true", onclick: () => pick("card_lost") }, icon("card"), t("isLost"));
    const stolen = h("button", { class: "choice", "aria-pressed": "false", onclick: () => pick("card_stolen") }, icon("alert"), t("isStolen"));
    const quick = h("div", { class: "chips wrap" });
    function pick(tr) {
      trigger = tr; lost.setAttribute("aria-pressed", tr === "card_lost"); stolen.setAttribute("aria-pressed", tr === "card_stolen");
      quick.replaceChildren(...t(tr === "card_lost" ? "quickLost" : "quickStolen").map((q) => h("button", { class: "chip", onclick: () => { words.value = q; begin.focus(); } }, q)));
    }
    const words = typed(h("textarea", { class: "field", rows: "2", placeholder: t("whatHappenedPh"), "aria-label": t("whatHappened") }));
    const begin = h("button", { class: "btn danger", onclick: async () => {
      if (!words.value.trim()) { words.focus(); return; }
      begin.disabled = true;
      try { render(await call("POST", "/rescue/start", { user_id: USER, trigger, text: words.value.trim(), lang: getLang() })); }
      catch (e) { box.prepend(h("div", { class: "error" }, errorText(e))); begin.disabled = false; }
    } }, t("startRescue"));
    box.replaceChildren(h("div", { class: "card" },
      h("p", { class: "muted" }, t("sosIntro")),
      lost, stolen, h("h2", { style: "margin-top:10px" }, t("whatHappened")), quick, words,
      h("p", { class: "muted small" }, t("tapOrType")), begin));
    pick("card_lost");
  }
  function render(r) {
    const st = r.rescue?.state_after;
    const at = Math.max(0, ORDER.indexOf(st));
    const card = h("div", { class: "card" },
      h("div", { class: "steps", "aria-hidden": "true" }, ORDER.map((_, i) => h("span", { class: i <= at ? "on" : "" }))),
      h("p", { class: "muted small" }, t("step", { s: t("steps")[st] ?? t("starting") })));
    replyNodes(r, render, true).forEach((n) => card.append(n));
    const doNow = r.rescue?.do_now;
    if (doNow === "answer_identity_question") {
      // The answer is sent once and not kept anywhere in the app.
      const ans = typed(h("input", { class: "field", type: "text", autocomplete: "off", placeholder: t("yourAnswer"), "aria-label": t("yourAnswer") }));
      card.append(ans, h("button", { class: "btn", onclick: async (ev) => { ev.currentTarget.disabled = true; await step({ text: ans.value }); } }, t("sendAnswer")));
    } else if (doNow === "choose_card") {
      card.append(h("h2", {}, t("whichCard")), ...(r.rescue.card_names || []).map((n) => h("button", { class: "choice", onclick: () => step({ text: n }) }, icon("card"), n)));
    } else if (doNow === "confirm_freeze" || doNow === "confirm_transfer_or_skip") {
      const token = r.confirmation?.confirmation_token;
      const actions = h("div", { class: "row" });
      if (doNow === "confirm_transfer_or_skip") actions.append(h("button", { class: "btn secondary", onclick: () => step({ text: "" }) }, t("noMoney")));
      actions.append(h("button", { class: "btn", onclick: (ev) => { ev.currentTarget.disabled = true; step({ text: "", confirmation_token: token }); } }, doNow === "confirm_freeze" ? t("freezeMine") : t("sendMoney")));
      card.append(actions);
    } else if (doNow === "locked") {
      card.append(h("div", { class: "error" }, t("locked")));
    } else if (doNow === "done") {
      card.append(h("button", { class: "btn secondary", onclick: () => go("activity") }, t("seeWhat")));
    }
    box.replaceChildren(card);
  }
  async function step(body) {
    try { render(await call("POST", "/rescue/step", { user_id: USER, lang: getLang(), ...body })); }
    catch (e) { box.prepend(h("div", { class: "error" }, errorText(e))); }
  }
}
function typed(el) { el.addEventListener("paste", (ev) => ev.preventDefault()); el.addEventListener("drop", (ev) => ev.preventDefault()); return el; }

// ---------- Activity ----------
// Ledger entries in plain words, the way a banking app lists them. Only what the entries say; the raw entries stay
// under Advanced. A receipt finds what it paid for through the proposal with the same idempotency key.
function friendly(entries) {
  const out = [];
  const actions = {};
  for (const e of entries) { const a = e.payload?.action; if (a?.idempotency_key) actions[a.idempotency_key] = a; }
  const add = (o, group) => out.push({ ...o, group });
  for (const e of entries) {
    const p = e.payload || {};
    if (e.kind === "receipt" && p.receipt) {
      const rc = p.receipt; const a = actions[rc.idempotency_key] || {};
      const done = rc.status === "completed";
      add({ ic: done ? "check" : "clock", tone: done ? "ok" : "", what: t("aSent", { purpose: t("purposes")[a.purpose] ?? t("aTransfer") }),
        sub: [a.payee_id ? t("aSentTo", { payee: t("payees")[a.payee_id] ?? nice(a.payee_id) }) : "", done ? "" : t("aPending"), rc.simulated ? t("simNote") : ""].filter(Boolean).join(" · "),
        amount: `−${money(rc.amount, rc.currency)}`, ts: e.ts }, "pay");
    } else if (e.kind === "decision" && p.decision && p.decision.allowed === false) {
      const paste = (p.decision.rule_ids || []).includes("R01");
      add({ ic: "ban", tone: "bad", what: paste ? t("aBlockedPaste") : t("aBlockedRule", { what: t("types")[p.action?.type] ?? t("aRequest") }),
        sub: paste ? t("aBlockedPasteSub") : t("aBlockedRuleSub"), ts: e.ts }, "blocked");
    } else if (e.kind === "note" && p.kind === "family_notice") {
      add({ ic: "family", what: t("aFamilyTold"), sub: p.to?.channel ? t("aFamilyBy", { channel: p.to.channel === "whatsapp" ? "WhatsApp" : nice(p.to.channel) }) : "", ts: e.ts }, "rescue");
    } else if (e.kind === "note" && p.kind === "rescue_started") {
      // Only the start shows; each step between states is a rescue_transition note, kept under Advanced.
      add({ ic: "buoy", what: t("aRescueStarted"), sub: "", ts: e.ts }, "rescue");
    } else if (e.kind === "note" && p.kind === "rescue_replacement") {
      add({ ic: "card", what: t("aReplace"), sub: t("aReplaceSub"), ts: e.ts }, "rescue");
    } else if (e.kind === "execution" && p.result?.freeze) {
      add({ ic: "snow", what: t("aFrozen"), sub: t("aFrozenSub"), ts: e.ts }, "rescue");
    }
  }
  return out.reverse();
}
function row(it) {
  const time = new Date(it.ts).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" });
  return h("li", {}, h("span", { class: `a-ic ${it.tone || ""}` }, icon(it.ic)),
    h("div", { class: "a-main" }, h("div", { class: "what" }, it.what), h("div", { class: "muted small" }, [it.sub, time].filter(Boolean).join(" · "))),
    it.amount ? h("span", { class: "a-amt" }, it.amount) : "");
}
// Groups the rows under Today, Yesterday or the date, newest first.
function byDay(items) {
  const groups = [];
  for (const it of items) {
    const d = days(it.ts);
    const label = d === 0 ? t("dayToday") : d === -1 ? t("dayYesterday") : new Date(it.ts).toLocaleDateString(locale(), { day: "numeric", month: "short" });
    if (!groups.length || groups[groups.length - 1].label !== label) groups.push({ label, rows: [] });
    groups[groups.length - 1].rows.push(row(it));
  }
  return groups.map((g) => h("section", { class: "day" }, h("h3", { class: "day-h" }, g.label), h("ul", { class: "list card" }, g.rows)));
}
function setBadge(el, v) {
  const ok = v.first_broken_seq === null || v.first_broken_seq === undefined;
  el.className = ok ? "badge" : "badge warn";
  el.replaceChildren(icon(ok ? "lock" : "alert"), h("span", {}, ok ? t("verified") : t("tampered", { n: v.first_broken_seq })));
}
async function activity() {
  const list = h("div", { class: "feed" }, h("p", { class: "muted" }, t("loading")));
  const badge = h("span", { class: "badge" }, t("checking"));
  const tech = h("div", { hidden: true });
  let items = [];
  const filters = h("div", { class: "filters", role: "group", "aria-label": t("show") });
  function draw(which) {
    filters.replaceChildren(...t("filters").map(([k, label]) => h("button", { "aria-pressed": k === which ? "true" : "false", onclick: () => draw(k) }, label)));
    const shown = which === "all" ? items : items.filter((i) => i.group === which);
    list.replaceChildren(...(shown.length ? byDay(shown) : [h("section", { class: "card" }, h("p", { class: "muted" }, which === "all" ? t("nothingYet") : t("nothingHere")))]));
  }
  view.append(h("h1", {}, t("activity")), h("p", {}, badge), filters, list,
    h("button", { class: "link", onclick: () => { tech.hidden = !tech.hidden; } }, t("advanced")), tech);
  draw("all");
  try {
    const [entries, verify] = await Promise.all([call("GET", `/ledger/${USER}`), call("GET", `/ledger/${USER}/verify`)]);
    items = friendly(entries);
    draw("all");
    setBadge(badge, verify);
    tech.replaceChildren(h("section", { class: "card" }, h("p", { class: "muted small" }, t("entries", { n: entries.length })),
      h("ul", { class: "list" }, entries.slice().reverse().map((e) => h("li", {}, h("span", { class: "tech" }, `#${e.seq} ${e.kind}${e.payload?.kind ? ": " + e.payload.kind : ""} · ${e.hash.slice(0, 10)}…`))))));
  } catch (e) { list.replaceChildren(h("p", { class: "muted" }, errorText(e))); badge.remove(); }
}

// ---------- Me: the safety net, findable after onboarding ----------
// The plan is the demo one in fixtures/demo_user.yaml (cards, identity check, emergency money, trusted contact Ana).
function me() {
  const item = (ic, what, sub) => h("li", {}, h("span", { class: "emoji ib" }, icon(ic)), h("div", {}, h("div", { class: "what" }, what), h("div", { class: "muted small" }, sub)));
  view.append(
    h("section", { class: "card trip-card" }, h("div", { class: "bal-head" }, h("h2", { style: "margin:0;flex:1" }, t("yourTrip")), h("button", { class: "link", onclick: () => go("setup", "me") }, t("change"))),
      h("p", { style: "margin:6px 0 0" }, trip ? tripLine() : h("span", { class: "muted" }, t("setupSub")))),
    h("div", { class: "bal-head" }, h("h1", { style: "flex:1" }, t("meTitle")), h("button", { class: "link", onclick: () => go("plan", { i: 0, back: "me" }) }, t("changePlan"))),
    h("p", { class: "muted", style: "margin:-6px 2px 14px" }, t("meSub")),
    h("section", { class: "card" }, h("ul", { class: "list" },
      netItems().map(([ic, what, sub]) => item(ic, what, sub)),
      mine ? "" : item("family", t("trusted"), t("trustedSub")))),
    routeTips(),
    h("section", { class: "card" }, h("h2", {}, t("account")), h("ul", { class: "list" }, item("user", t("signedInAs"), t("signedInSub")))),
    h("button", { class: "card roadmap-link", onclick: () => go("roadmap") }, icon("map"), h("span", {}, t("roadmapLink")), icon("chev", "chev-r")));
}

// ---------- Help and the roadmap ----------
function help() {
  view.append(h("h1", {}, t("help")),
    h("section", { class: "card" }, t("faq").map(([q, a]) => h("details", { class: "faq" }, h("summary", {}, h("span", {}, q), icon("chev")), h("p", {}, a)))),
    h("button", { class: "card roadmap-link", onclick: () => go("roadmap") }, icon("map"), h("span", {}, t("roadmapLink")), icon("chev", "chev-r")));
}
// Planned, not built: each line says what exists today, so nothing on this screen claims a feature that is not there.
function roadmap() {
  view.append(h("h1", {}, t("roadmap")), h("p", { class: "muted", style: "margin:-6px 2px 14px" }, t("roadmapSub")),
    h("section", { class: "card" }, h("ul", { class: "list" }, t("roadmapItems").map(([, what, sub], i) =>
      h("li", {}, h("span", { class: "emoji ib" }, icon(["lock", "shield", "cash", "family", "sparkle", "card", "home"][i] || "sparkle")), h("div", {}, h("div", { class: "what" }, what), h("div", { class: "muted small" }, sub)))))));
}

// ---------- 404: the line goes flat ----------
function lost() {
  const flat = "M0 60h70l10-30 14 60 12-44 8 14h46l10-30 14 60 12-44 8 14h40l8-16 10 30 8-14h12 L520 60";
  const box = h("div", { class: "monitor", "aria-hidden": "true" });
  box.innerHTML = `<svg viewBox="0 0 520 120" preserveAspectRatio="none"><path class="trace" d="${flat}"/><circle class="dot" cx="508" cy="60" r="5"/></svg>`;
  view.append(h("div", { class: "lost" }, box,
    h("p", { class: "code" }, t("e404")), h("h1", {}, t("flatlined")), h("p", {}, t("flatSub")),
    h("button", { class: "btn", onclick: () => go("home") }, t("backHome"))));
}

// A known screen in the address, such as #chat, opens it; anything else is the 404. ?lang=pt or ?lang=zh picks a language.
const asked = new URLSearchParams(location.search).get("lang");
setLang(LANGS.some(([c]) => c === asked) ? asked : "en");
paintChrome();
// Ask the API once whether it is there, so the pill says the same thing on every screen.
fetch(API + "/health").catch(() => { usingSample = true; paintPill(); });
const first = location.hash.slice(1);
go(first === "" ? "welcome" : first in screens ? first : "lost");
