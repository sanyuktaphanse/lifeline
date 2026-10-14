// Lifeline mockup, phone first. Talks to the real Lifeline API that `make dev` starts (docs/api.md).
// Rules kept from docs/api.md and app/: server text is only ever set as text, never as HTML; a confirmation token
// lives in memory inside its card and is sent back once; pasted text goes in `pasted_text`, never in `text`; the
// rescue takes only typed words and the identity answer is never stored. Nothing is kept in browser storage.

import { sample } from "./sample.js";
import { LANGS, getLang, setLang, t } from "./i18n.js";

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
const nice = (s) => String(s ?? "").replace(/_/g, " ");
const tag = (label) => h("span", { class: "tag" }, label);
const drawTrace = (el) => { el.innerHTML = `<svg viewBox="0 0 48 24" aria-hidden="true"><path class="trace" d="${PULSE}"/></svg>`; }; // a fixed drawing, never server text

// ---------- navigation and language ----------
const view = document.getElementById("view");
const tabs = [...document.querySelectorAll(".tabs button")];
const screens = { welcome, hello, soon, home, chat, sos, activity, help, roadmap, lost };
const FULL = new Set(["welcome", "hello", "soon", "lost"]);
let currentScreen = "welcome";
function go(name, arg) {
  currentScreen = name;
  tabs.forEach((b) => (b.dataset.tab === name ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  view.replaceChildren();
  view.classList.remove("chatting");
  document.body.classList.toggle("signin", FULL.has(name));
  screens[name](arg);
  window.scrollTo(0, 0);
  view.focus({ preventScroll: true });
}
tabs.forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));
function paintChrome() {
  const names = { home: "tabHome", chat: "tabChat", sos: "tabSos", activity: "tabActivity", help: "tabHelp" };
  tabs.forEach((b) => { const label = t(names[b.dataset.tab]); b.setAttribute("aria-label", label); b.lastElementChild.textContent = label; });
  paintPill();
  document.querySelectorAll(".lang").forEach((sel) => { sel.value = getLang(); sel.setAttribute("aria-label", t("language")); });
}
function langPicker(extraClass = "") {
  const sel = h("select", { class: `lang ${extraClass}`, "aria-label": t("language"), onchange: (e) => { setLang(e.target.value); paintChrome(); go(currentScreen); } },
    LANGS.map(([code, short, name]) => h("option", { value: code, title: name }, short)));
  sel.value = getLang();
  return sel;
}
document.querySelector(".top").append(langPicker());

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
    h("div", { class: "w-top" }, h("h1", {}, a, h("em", {}, b), c)),
    h("div", { class: "w-mid" }, h("span", { class: "aura", "aria-hidden": "true" }), orb),
    h("div", { class: "w-bottom" },
      h("button", { class: "btn", onclick: () => go("hello") }, t("tryDemo")),
      h("div", { class: "sso-row" }, icon("Email", "icons/mail.png"), icon("Apple", "icons/apple.png"), icon("Google", "icons/google.png")),
      h("p", { class: "fine" }, t("signinSoon"))),
  );
}

// After Try the demo: the demo plan in fixtures/demo_user.yaml as docs/api.md, "Rescue", states it. Nothing is asked.
function hello() {
  view.append(
    h("div", { class: "hello" }, h("span", { class: "wave", "aria-hidden": "true" }, "👋"), h("h1", {}, t("helloTitle")), h("p", {}, t("helloSub"))),
    h("section", { class: "card" }, h("h2", {}, t("safetyNet")), h("p", { class: "muted small" }, t("safetyIntro")),
      h("ul", { class: "list" }, t("plan").map(([e, what, sub]) => h("li", {}, h("span", { class: "emoji", "aria-hidden": "true" }, e), h("div", {}, h("div", { class: "what" }, what), h("div", { class: "muted small" }, sub)))))),
    h("p", { class: "muted small", style: "text-align:center" }, t("ownPlanSoon")),
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
    h("button", { class: "btn", onclick: () => go("hello") }, t("tryDemo")),
    h("button", { class: "link center", onclick: () => go("welcome") }, t("soonBack"))));
}

// ---------- Home: a calm assistant home, four live cards and the message box ----------
async function home() {
  const orb = h("div", { class: "orb mini-orb", "aria-hidden": "true" }); drawTrace(orb);
  const rentSub = h("span", { class: "sub" }, t("cRentSub"));
  const badge = h("span", { class: "badge" }, t("checking"));
  const count = h("span", { class: "count", hidden: true });
  const card = (cls, icon, title, sub, onclick) => h("button", { class: `tile ${cls}`, onclick }, h("span", { class: "ico", "aria-hidden": "true" }, icon), h("span", { class: "ttl" }, title), sub);
  const [q0, q1, q2, q3] = t("quick");
  const ask = h("textarea", { class: "msg", rows: "2", placeholder: t("askPh"), "aria-label": t("yourMessage") });
  const sendIt = () => { const v = ask.value.trim(); if (v) go("chat", { prompt: v, send: true }); else ask.focus(); };
  ask.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendIt(); } });
  // A paste here is someone else's words, so it opens Chat with the message attached rather than as the student's own.
  ask.addEventListener("paste", (e) => { const v = e.clipboardData?.getData("text") ?? ""; if (!v) return; e.preventDefault(); go("chat", { prompt: ask.value, pasted: v }); });
  view.append(
    h("div", { class: "home-hero" },
      h("button", { class: "bell", "aria-label": t("reminders"), onclick: () => go("chat", { prompt: t("more")[1] }) }, "🔔", count), orb, h("p", { class: "muted" }, t("homeHello")),
      h("h1", {}, t("homeHead")[0], h("br"), h("span", { class: "soft" }, t("homeHead")[1]))),
    h("div", { class: "tiles" },
      card("rent", "🏠", t("cRent"), rentSub, () => go("chat", q0)),
      card("lost", "🛟", t("cLost"), h("span", { class: "sub" }, t("cLostSub")), () => go("sos")),
      card("home", "📦", t("cHome"), h("span", { class: "sub" }, t("cHomeSub")), () => go("chat", q1)),
      card("scam", "🛡️", t("cScam"), h("span", { class: "sub" }, t("cScamSub")), () => go("chat", q2))),
    h("div", { class: "glow-box" }, ask,
      h("div", { class: "glow-actions" }, h("button", { class: "iconbtn", "aria-label": t("attach"), onclick: () => go("chat", { prompt: ask.value, attach: true }) }, "📎"),
        h("span", { style: "flex:1" }), h("button", { class: "iconbtn send", "aria-label": t("send"), onclick: sendIt }, "➤"))),
    h("div", { class: "home-foot" }, h("button", { class: "link", onclick: () => go("activity") }, badge), h("button", { class: "link", onclick: () => go("roadmap") }, t("whatsNext"))),
  );
  try {
    const r = await call("GET", `/reminders/${USER}`);
    const items = [...(r.due || []), ...(r.upcoming || [])];
    if (items.length) rentSub.textContent = t("dueIn", { text: items[0].text, when: when(items[0].due) });
    if ((r.due || []).length) { count.textContent = String(r.due.length); count.hidden = false; count.setAttribute("aria-label", t("due", { n: r.due.length })); }
  } catch { /* the card keeps its plain subtitle */ }
  try { setBadge(badge, await call("GET", `/ledger/${USER}/verify`)); } catch { badge.remove(); }
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
  const send = h("button", { class: "iconbtn send", "aria-label": t("send"), onclick: () => submit() }, "➤");
  const clip = h("button", { class: "iconbtn", "aria-label": t("attach"), title: t("attach"), onclick: () => { attached.hidden = false; pasteBox.focus(); } }, "📎");
  // A paste into the message box is someone else's words, so it moves to the attached message.
  msg.addEventListener("paste", (ev) => {
    const text = ev.clipboardData?.getData("text") ?? "";
    if (!text) return;
    ev.preventDefault();
    pasteBox.value = (pasteBox.value ? pasteBox.value + "\n" : "") + text;
    attached.hidden = false;
  });
  const chips = h("div", { class: "chips" },
    t("quick").map((q) => h("button", { class: "chip top", onclick: () => use(q) }, `${q.emoji} ${q.label}`)),
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

  view.classList.add("chatting");
  view.append(h("h1", {}, t("chat")), list, h("div", { class: "composer" }, chips, attached, h("div", { class: "line" }, clip, msg, send)));
  list.append(...thread);
  if (thread.length === 0) list.append(answer(t("hello"), false));
  if (seed) { use(seed); if (seed.send) submit(); }
}

// Turns an AgentReply into nodes, in the order docs/api.md "Reading an AgentReply" gives.
function replyNodes(r, onReply) {
  const out = [];
  let body = r.text || "";
  for (const s of r.blocked || []) { out.push(h("div", { class: "blocked" }, t("blocked"), s)); body = body.replace(s, ""); }
  if (r.turn_summary) body = body.replace(r.turn_summary, "");
  body = body.trim();
  if (body) out.push(answer(body, r.sample));
  if (r.receipt) out.push(receiptCard(r.receipt));
  if (r.freeze) out.push(h("div", { class: "bubble bot" }, t("freeze", { s: nice(r.freeze.status) }), r.freeze.deep_link ? h("a", { href: r.freeze.deep_link, target: "_blank", rel: "noopener" }, t("openCardApp")) : ""));
  if (r.cancel) out.push(h("div", { class: "bubble bot" }, t("cancel", { s: nice(r.cancel.status) }), r.cancel.reason ? `. ${r.cancel.reason}` : ""));
  if (r.confirmation) out.push(paymentSheet(r.confirmation, onReply));
  if (r.turn_summary) out.push(h("div", { class: "summary" }, "✓ ", r.turn_summary));
  return out;
}
function answer(text, isSample) {
  const mini = h("span", { class: "mini", "aria-hidden": "true" }); drawTrace(mini);
  const copy = h("button", { class: "chipbtn", onclick: async () => { try { await navigator.clipboard.writeText(text); copy.textContent = t("copied"); } catch { /* the text stays selectable */ } } }, "⧉ ", t("copy"));
  return h("div", { class: "answer" },
    h("div", { class: "who" }, mini, h("span", {}, t("answer")), isSample ? tag(t("sample")) : ""),
    h("p", {}, text), h("div", { class: "answer-actions" }, copy));
}
function receiptCard(rc) {
  return h("div", { class: "card sheet" },
    h("h2", {}, rc.status === "completed" ? t("sent") : t("transferStatus", { s: nice(rc.status) })),
    h("p", { class: "amount" }, money(rc.amount, rc.currency)),
    h("p", { class: "muted" }, t("via", { rail: rc.rail, id: rc.receipt_id }), rc.simulated ? tag(t("simulated")) : ""));
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
    rows.push(line(t("viaLabel"), sel.rail, sel.simulated ? tag(t("simulated")) : ""));
    rows.push(line(t("fee"), money(fee, sel.currency_from)));
    if (fx) rows.push(line(t("fx"), money(fx, sel.currency_from)));
    rows.push(line(t("arrives"), arrive(sel.arrival_hours)));
    if (a.amount) rows.push(h("div", { class: "sheet-row total" }, h("span", {}, t("total")), h("span", {}, money(Number(a.amount) + fee + fx, a.currency))));
  }
  const routes = (c.routes || []).map((rt) => {
    const on = sel && rt.rail === sel.rail;
    const off = rt.blocked_reason || rt.limit_ok === false || rt.status === "down";
    return h("div", { class: `route${on ? " sel" : ""}${off ? " off" : ""}` },
      h("span", {}, on ? "● " : "○ ", rt.rail, rt.simulated ? tag(t("simulated")) : ""),
      h("span", { class: "muted" }, off ? t("blockedRoute") : t("feeShort", { fee: money(rt.fee, rt.currency_from), t: arrive(rt.arrival_hours) })));
  });
  const timer = h("span", {});
  const yes = h("button", { class: "btn", onclick: async () => {
    if (!token) return;
    const tk = token; token = null; stop(); yes.disabled = no.disabled = true; yes.textContent = t("sending");
    try { onReply(await call("POST", "/confirm", { user_id: USER, confirmation_token: tk, lang: getLang() })); }
    catch (e) { onReply({ text: errorText(e), blocked: [], turn_summary: null }); }
    yes.textContent = t("confirmed");
  } }, a.type === "transfer" ? t("confirmSend") : t("confirmBtn"));
  const no = h("button", { class: "link", onclick: () => { token = null; stop(); yes.disabled = no.disabled = true; no.textContent = t("notSent"); } }, t("notNow"));
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
    routes.length > 1 ? h("details", { class: "compare" }, h("summary", {}, t("compare", { n: routes.length })), h("div", { class: "routes" }, routes)) : "",
    h("div", { class: "warn" }, "⚠️ ", t("warnings")[c.warning_key] ?? t("checkFirst")),
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
    const lost = h("button", { class: "choice", "aria-pressed": "true", onclick: () => pick("card_lost") }, t("isLost"));
    const stolen = h("button", { class: "choice", "aria-pressed": "false", onclick: () => pick("card_stolen") }, t("isStolen"));
    function pick(tr) { trigger = tr; lost.setAttribute("aria-pressed", tr === "card_lost"); stolen.setAttribute("aria-pressed", tr === "card_stolen"); }
    const words = typed(h("textarea", { class: "field", rows: "3", placeholder: t("whatHappenedPh"), "aria-label": t("whatHappened") }));
    const begin = h("button", { class: "btn danger", onclick: async () => {
      if (!words.value.trim()) { words.focus(); return; }
      begin.disabled = true;
      try { render(await call("POST", "/rescue/start", { user_id: USER, trigger, text: words.value.trim(), lang: getLang() })); }
      catch (e) { box.prepend(h("div", { class: "error" }, errorText(e))); begin.disabled = false; }
    } }, t("startRescue"));
    box.replaceChildren(h("div", { class: "card" },
      h("p", { class: "muted" }, t("sosIntro")),
      lost, stolen, h("h2", { style: "margin-top:10px" }, t("whatHappened")), words,
      h("p", { class: "muted small" }, t("noPaste")), begin));
  }
  function render(r) {
    const st = r.rescue?.state_after;
    const at = Math.max(0, ORDER.indexOf(st));
    const card = h("div", { class: "card" },
      h("div", { class: "steps", "aria-hidden": "true" }, ORDER.map((_, i) => h("span", { class: i <= at ? "on" : "" }))),
      h("p", { class: "muted small" }, t("step", { s: t("steps")[st] ?? t("starting") })));
    replyNodes(r, render).forEach((n) => card.append(n));
    const doNow = r.rescue?.do_now;
    if (doNow === "answer_identity_question") {
      // The answer is sent once and not kept anywhere in the app.
      const ans = typed(h("input", { class: "field", type: "text", autocomplete: "off", "aria-label": t("yourAnswer") }));
      card.append(ans, h("button", { class: "btn", onclick: async (ev) => { ev.currentTarget.disabled = true; await step({ text: ans.value }); } }, t("sendAnswer")));
    } else if (doNow === "choose_card") {
      card.append(h("h2", {}, t("whichCard")), ...(r.rescue.card_names || []).map((n) => h("button", { class: "choice", onclick: () => step({ text: n }) }, "💳 ", n)));
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
// Ledger entries in plain words. Only what the entries say; anything else stays in the technical view.
function friendly(entries) {
  const out = [];
  const add = (o, group) => out.push({ ...o, group });
  for (const e of entries) {
    const p = e.payload || {};
    if (e.kind === "receipt" && p.receipt) {
      const rc = p.receipt;
      add({ emoji: rc.status === "completed" ? "✅" : "⏳", what: t("aPaid", { amount: money(rc.amount, rc.currency), rail: rc.rail }), sub: `${nice(rc.status)}${rc.simulated ? " · " + t("isSimulated") : ""}`, ts: e.ts }, "pay");
    } else if (e.kind === "decision" && p.decision && p.decision.allowed === false) {
      add({ emoji: "⛔", what: t("aBlocked", { what: t("types")[p.action?.type] ?? t("aRequest") }), sub: t("rules", { r: (p.decision.rule_ids || []).join(", ") }), ts: e.ts }, "blocked");
    } else if (e.kind === "note" && p.kind === "family_notice") {
      add({ emoji: "👪", what: t("aFamily"), sub: t("aFamilySub"), ts: e.ts }, "rescue");
    } else if (e.kind === "note" && /^rescue_/.test(p.kind || "")) {
      add({ emoji: "🛟", what: t("aRescue", { what: nice(p.kind.replace("rescue_", "")) }), sub: "", ts: e.ts }, "rescue");
    } else if (e.kind === "execution" && p.result?.freeze) {
      add({ emoji: "🧊", what: t("aFreeze"), sub: nice(p.result.freeze.status), ts: e.ts }, "rescue");
    }
  }
  return out.reverse();
}
function row(it) { return h("li", {}, h("span", { class: "emoji", "aria-hidden": "true" }, it.emoji), h("div", {}, h("div", { class: "what" }, it.what), h("div", { class: "muted small" }, [it.sub, when(it.ts)].filter(Boolean).join(" · ")))); }
function setBadge(el, v) {
  const ok = v.first_broken_seq === null || v.first_broken_seq === undefined;
  el.className = ok ? "badge" : "badge warn";
  el.textContent = ok ? t("verified") : t("tampered", { n: v.first_broken_seq });
}
async function activity() {
  const list = h("ul", { class: "list" }, h("li", {}, h("span", { class: "muted" }, t("loading"))));
  const badge = h("span", { class: "badge" }, t("checking"));
  const tech = h("div", { hidden: true });
  let items = [];
  const filters = h("div", { class: "filters", role: "group", "aria-label": t("show") });
  function draw(which) {
    filters.replaceChildren(...t("filters").map(([k, label]) => h("button", { "aria-pressed": k === which ? "true" : "false", onclick: () => draw(k) }, label)));
    const shown = which === "all" ? items : items.filter((i) => i.group === which);
    list.replaceChildren(...(shown.length ? shown.map(row) : [h("li", {}, h("span", { class: "muted" }, which === "all" ? t("nothingYet") : t("nothingHere")))]));
  }
  view.append(h("h1", {}, t("activity")), h("p", {}, badge), filters, h("section", { class: "card" }, list),
    h("button", { class: "link", onclick: () => { tech.hidden = !tech.hidden; } }, t("advanced")), tech);
  draw("all");
  try {
    const [entries, verify] = await Promise.all([call("GET", `/ledger/${USER}`), call("GET", `/ledger/${USER}/verify`)]);
    items = friendly(entries);
    draw("all");
    setBadge(badge, verify);
    tech.replaceChildren(h("section", { class: "card" }, h("p", { class: "muted small" }, t("entries", { n: entries.length })),
      h("ul", { class: "list" }, entries.slice().reverse().map((e) => h("li", {}, h("span", { class: "tech" }, `#${e.seq} ${e.kind}${e.payload?.kind ? ": " + e.payload.kind : ""} · ${e.hash.slice(0, 10)}…`))))));
  } catch (e) { list.replaceChildren(h("li", {}, h("span", { class: "muted" }, errorText(e)))); badge.remove(); }
}

// ---------- Help and the roadmap ----------
function help() {
  view.append(h("h1", {}, t("help")),
    h("section", { class: "card" }, t("faq").map(([q, a]) => h("details", { class: "faq" }, h("summary", {}, q), h("p", {}, a)))),
    h("button", { class: "card roadmap-link", onclick: () => go("roadmap") }, h("span", { "aria-hidden": "true" }, "🗺️"), h("span", {}, t("roadmapLink")), h("span", { "aria-hidden": "true" }, "›")));
}
// Planned, not built: each line says what exists today, so nothing on this screen claims a feature that is not there.
function roadmap() {
  view.append(h("h1", {}, t("roadmap")), h("p", { class: "muted", style: "margin:-6px 2px 14px" }, t("roadmapSub")),
    h("section", { class: "card" }, h("ul", { class: "list" }, t("roadmapItems").map(([e, what, sub]) =>
      h("li", {}, h("span", { class: "emoji", "aria-hidden": "true" }, e), h("div", {}, h("div", { class: "what" }, what, tag(t("soon"))), h("div", { class: "muted small" }, sub)))))));
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
const first = location.hash.slice(1);
go(first === "" ? "welcome" : first in screens ? first : "lost");
