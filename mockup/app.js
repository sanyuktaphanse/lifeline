// Lifeline mockup, phone first. Talks to the real Lifeline API that `make dev` starts (docs/api.md).
// Rules kept from docs/api.md and app/: server text is only ever set as text, never as HTML; a confirmation token
// lives in memory inside its card and is sent back once; pasted text goes in `pasted_text`, never in `text`; the
// rescue takes only typed words and the identity answer is never stored. Nothing is kept in browser storage.

import { sample } from "./sample.js";

const API = "http://127.0.0.1:8000";
// When no API answers at all, as on a hosted preview, the screens fill with labelled sample data instead.
let usingSample = false;
function markSample() {
  if (usingSample) return;
  usingSample = true;
  const pill = document.querySelector(".demo-pill");
  if (pill) { pill.textContent = "Preview · sample data"; pill.title = "No Lifeline server is running here, so these screens show sample data. Nothing moves."; }
}
const USER = "student_001"; // fixture: the demo student, fixtures/demo_user.yaml. There is no sign in yet.

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
async function call(method, path, body) {
  let res;
  try {
    res = await fetch(API + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  } catch {
    const fake = sample(method, path, body);
    if (fake !== null) { markSample(); return structuredClone(fake); }
    throw { status: 0, detail: "Lifeline's server is not running on this computer. Start it with make dev." };
  }
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) throw { status: res.status, detail: data?.detail ?? res.statusText };
  return data;
}
const errorText = (e) => (typeof e?.detail === "string" ? e.detail : e?.detail?.reasons?.join(" ") || "Something went wrong, and nothing was done.");
const money = (amount, cur) => { const n = Number(amount); const d = Number.isInteger(n) ? 0 : 2; return `${n.toLocaleString("en-SG", { minimumFractionDigits: d, maximumFractionDigits: 2 })} ${cur ?? ""}`.trim(); };
const when = (iso) => new Date(iso).toLocaleString("en-SG", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const PAYEES = { landlord_sp: "your landlord in São Paulo", self_sg: "your own Singapore account" };
const payee = (id) => PAYEES[id] ?? id;
const WARNINGS = {
  "warn.transfer.irreversible": "Once sent, a transfer usually cannot be taken back.",
  "warn.payee.new": "A new payee waits 24 hours before it can be paid.",
  "warn.freeze.card": "Freezing stops every payment on this card until you unfreeze it.",
  "warn.standing.new": "This payment will then run every month by itself, within the pattern you confirm.",
  "warn.transfer.cancel": "Cancelling stops this transfer if the provider still allows it.",
};

// ---------- navigation ----------
const view = document.getElementById("view");
const tabs = [...document.querySelectorAll(".tabs button")];
const screens = { welcome, hello, home, chat, sos, activity, help, lost };
function go(name, arg) {
  tabs.forEach((b) => (b.dataset.tab === name ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  view.replaceChildren();
  view.classList.remove("chatting");
  document.body.classList.toggle("signin", name === "welcome" || name === "hello" || name === "lost");
  screens[name](arg);
  view.scrollTop = 0;
  view.focus({ preventScroll: true });
}
tabs.forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));

// ---------- Home ----------
const QUICK = [
  { emoji: "🏠", label: "Pay rent", prompt: "Pay this month's rent of 1,200 SGD to my landlord in Brazil" },
  { emoji: "📦", label: "Where's my parents' money?", prompt: "My parents sent me money from China and it hasn't arrived. Where is it?" },
  { emoji: "🛡️", label: "Is this a scam?", prompt: "Is this message a scam?", attach: true },
  { emoji: "💰", label: "My balance", prompt: "What's my balance?" },
];
async function home() {
  const next = h("p", { class: "muted" }, "Loading…");
  const recent = h("ul", { class: "list" }, h("li", {}, h("span", { class: "muted" }, "Loading…")));
  const badge = h("span", { class: "badge" }, "🔒 Checking your history…");
  const count = h("span", { class: "count", hidden: true });
  const comingUp = h("section", { class: "card" }, h("h2", {}, "📅  Coming up"), next);
  view.append(
    h("div", { class: "greet" },
      h("div", {}, h("h1", {}, "Hi there 👋"), h("p", {}, "How can Lifeline help today?")),
      h("button", { class: "bell", "aria-label": "Reminders", onclick: () => comingUp.scrollIntoView({ behavior: "smooth", block: "center" }) }, "🔔", count)),
    h("button", { class: "card sos-card", onclick: () => go("sos") },
      h("span", { class: "big", "aria-hidden": "true" }, "🛟"),
      h("div", {}, h("h2", {}, "Lost your card?"), h("p", {}, "Freeze it and get emergency money, step by step."))),
    comingUp,
    h("section", {}, h("div", { class: "grid2" }, QUICK.map((q) =>
      h("button", { class: "action", onclick: () => go("chat", q) }, h("span", { class: "emoji", "aria-hidden": "true" }, q.emoji), q.label)))),
    h("div", { style: "height:14px" }),
    h("section", { class: "card" }, h("h2", {}, "Recent activity"), recent, h("p", {}, badge),
      h("button", { class: "link", onclick: () => go("activity") }, "See all activity")),
  );
  try {
    const r = await call("GET", `/reminders/${USER}`);
    const items = [...(r.due || []), ...(r.upcoming || [])];
    next.textContent = items.length ? `${items[0].text} · ${when(items[0].due)}` : "Nothing scheduled. Ask Lifeline to remind you before rent is due.";
    if ((r.due || []).length) { count.textContent = String(r.due.length); count.hidden = false; count.setAttribute("aria-label", `${r.due.length} due`); }
  } catch (e) { next.textContent = errorText(e); }
  try {
    const [entries, verify] = await Promise.all([call("GET", `/ledger/${USER}`), call("GET", `/ledger/${USER}/verify`)]);
    const items = friendly(entries).slice(0, 3);
    recent.replaceChildren(...(items.length ? items.map(row) : [h("li", {}, h("span", { class: "muted" }, "No activity yet."))]));
    setBadge(badge, verify);
  } catch (e) { recent.replaceChildren(h("li", {}, h("span", { class: "muted" }, errorText(e)))); badge.remove(); }
}

// ---------- Chat ----------
const MORE = [
  "Set up my rent to pay automatically every month",
  "Remind me 3 days before rent is due",
  "Send 300 SGD emergency money to my own account",
  "Before I set up Pix, what will they ask?",
  "How much cash can I still take out on my Chinese cards?",
  "Show my monthly summary",
];
const thread = []; // what the chat shows, kept only while the page is open
function chat(seed) {
  const list = h("div", { class: "thread", "aria-live": "polite" });
  const msg = h("textarea", { class: "msg", rows: "1", placeholder: "Message Lifeline", "aria-label": "Your message" });
  const pasteBox = h("textarea", { "aria-label": "The message you received", placeholder: "Paste the message here" });
  const attached = h("div", { class: "attached", hidden: true },
    h("span", { class: "label" }, "Message you received"), pasteBox,
    h("button", { class: "link", onclick: () => { pasteBox.value = ""; attached.hidden = true; } }, "Remove"));
  const send = h("button", { class: "iconbtn send", "aria-label": "Send", onclick: () => submit() }, "➤");
  const clip = h("button", { class: "iconbtn", "aria-label": "Add a message you received", title: "Add a message you received", onclick: () => { attached.hidden = false; pasteBox.focus(); } }, "📎");
  // A paste into the message box is someone else's words, so it moves to the attached message.
  msg.addEventListener("paste", (ev) => {
    const text = ev.clipboardData?.getData("text") ?? "";
    if (!text) return;
    ev.preventDefault();
    pasteBox.value = (pasteBox.value ? pasteBox.value + "\n" : "") + text;
    attached.hidden = false;
  });
  const chips = h("div", { class: "chips" },
    QUICK.map((q) => h("button", { class: "chip top", onclick: () => use(q) }, `${q.emoji} ${q.label}`)),
    h("button", { class: "chip", onclick: (ev) => { ev.currentTarget.remove(); MORE.forEach((p) => chips.append(h("button", { class: "chip", onclick: () => use({ prompt: p }) }, p))); } }, "More ideas…"));
  function use(q) { msg.value = q.prompt; if (q.attach) { attached.hidden = false; pasteBox.focus(); } else msg.focus(); }

  async function submit() {
    const text = msg.value.trim();
    const pasted = attached.hidden ? "" : pasteBox.value.trim();
    if (!text) { push(h("div", { class: "error" }, pasted ? "Type your own question too. A message someone sent you is never sent on its own." : "Type what you need first.")); return; }
    push(h("div", { class: "bubble me" }, text));
    if (pasted) push(h("div", { class: "bubble quoted" }, h("span", { class: "label" }, "Message you received"), pasted));
    msg.value = ""; pasteBox.value = ""; attached.hidden = true; send.disabled = true;
    const typing = h("div", { class: "thinking" }, h("span", { class: "mini", "aria-hidden": "true" }), "Lifeline is thinking…");
    typing.firstChild.innerHTML = `<svg viewBox="0 0 48 24"><path class="trace" d="${PULSE}"/></svg>`;
    list.append(typing);
    try {
      const body = { user_id: USER, text };
      if (pasted) body.pasted_text = pasted;
      showReply(await call("POST", "/chat", body));
    } catch (e) {
      push(h("div", { class: "error" }, e.status === 503 || /API_KEY/.test(errorText(e)) ? `Lifeline's AI is not set up on this computer yet, so nothing was done. (${errorText(e)})` : errorText(e)));
    } finally { typing.remove(); send.disabled = false; }
  }
  function push(node) { thread.push(node); list.append(node); node.scrollIntoView({ block: "end", behavior: "smooth" }); }
  function showReply(r) { replyNodes(r, (n) => push(n), showReply).forEach(push); }

  view.classList.add("chatting");
  view.append(h("h1", {}, "Chat"), list,
    h("div", { class: "composer" }, chips, attached, h("div", { class: "line" }, clip, msg, send)));
  list.append(...thread);
  if (thread.length === 0) list.append(h("div", { class: "bubble bot" }, "Hi! Tell me what you need, like paying rent or checking a message. Nothing moves until you confirm."));
  if (seed) use(seed);
}

// Turns an AgentReply into chat nodes, in the order docs/api.md "Reading an AgentReply" gives.
function replyNodes(r, push, onReply) {
  const out = [];
  let body = r.text || "";
  for (const s of r.blocked || []) { out.push(h("div", { class: "blocked" }, "⛔ Blocked: ", s)); body = body.replace(s, ""); }
  if (r.turn_summary) body = body.replace(r.turn_summary, "");
  body = body.trim();
  if (body) out.push(h("div", { class: "bubble bot" }, body, r.sample ? h("span", { class: "tag" }, "Sample") : ""));
  if (r.receipt) out.push(receiptCard(r.receipt));
  if (r.freeze) out.push(h("div", { class: "bubble bot" }, `Card freeze: ${r.freeze.status.replace("_", " ")}`, r.freeze.deep_link ? h("a", { href: r.freeze.deep_link, target: "_blank", rel: "noopener" }, " Open your card app") : ""));
  if (r.cancel) out.push(h("div", { class: "bubble bot" }, `Cancel: ${r.cancel.status.replace("_", " ")}${r.cancel.reason ? ". " + r.cancel.reason : ""}`));
  if (r.confirmation) out.push(confirmCard(r.confirmation, onReply));
  if (r.turn_summary) out.push(h("div", { class: "summary" }, "✓ ", r.turn_summary));
  return out;
}
function receiptCard(rc) {
  const ok = rc.status === "completed";
  return h("div", { class: "card confirm" },
    h("h2", {}, ok ? "✅ Sent" : `Transfer ${rc.status.replace("_", " ")}`),
    h("p", { class: "amount" }, money(rc.amount, rc.currency)),
    h("p", { class: "muted" }, `via ${rc.rail} · receipt ${rc.receipt_id}`, rc.simulated ? h("span", { class: "tag" }, "Simulated") : ""));
}
function confirmCard(c, onReply) {
  const a = c.action || {};
  let token = c.confirmation_token; // in memory only, sent back once
  const routes = (c.routes || []).map((rt) => {
    const sel = c.selected_route && rt.rail === c.selected_route.rail;
    const off = rt.blocked_reason || rt.limit_ok === false || rt.status === "down";
    return h("div", { class: `route${sel ? " sel" : ""}${off ? " off" : ""}` },
      h("span", {}, sel ? "● " : "○ ", rt.rail, rt.simulated ? h("span", { class: "tag" }, "Simulated") : ""),
      h("span", { class: "muted" }, off ? "Blocked" : `fee ${money(rt.fee, rt.currency_from)} · ${rt.arrival_hours}h`));
  });
  const yes = h("button", { class: "btn", onclick: async () => {
    if (!token) return;
    const t = token; token = null; yes.disabled = no.disabled = true; yes.textContent = "Sending…";
    try { onReply(await call("POST", "/confirm", { user_id: USER, confirmation_token: t })); }
    catch (e) { onReply({ text: errorText(e), blocked: [], turn_summary: null }); }
    yes.textContent = "Confirmed";
  } }, "Confirm");
  const no = h("button", { class: "btn secondary", onclick: () => { token = null; yes.disabled = no.disabled = true; no.textContent = "Not sent"; } }, "Not now");
  return h("div", { class: "card confirm" },
    h("h2", {}, "Please confirm"),
    a.amount ? h("p", { class: "amount" }, money(a.amount, a.currency)) : "",
    h("p", { class: "muted" }, [a.type?.replace("_", " "), a.payee_id ? `to ${payee(a.payee_id)}` : "", a.purpose ? `for ${a.purpose}` : ""].filter(Boolean).join(" ")),
    routes.length ? h("div", { class: "routes" }, routes) : "",
    h("div", { class: "warn" }, "⚠️ ", WARNINGS[c.warning_key] ?? "Please check this before you confirm."),
    h("p", { class: "muted small" }, `This confirmation expires in ${Math.round((c.expires_in_seconds || 300) / 60)} minutes.`),
    h("div", { class: "row" }, no, yes));
}

// ---------- Lost card ----------
const STEP_NAMES = { S1: "Check it's you", S2: "Freeze the card", S3: "Phone wallet", S4: "Switch to backup", S5: "Emergency money", S6: "No backup", S7: "Replacement", S8: "Update your plan", S9: "Tell family", done: "Done" };
const ORDER = ["S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9", "done"];
function sos() {
  const box = h("div", {});
  view.append(h("h1", {}, "Lost card"), box);
  start();
  function start() {
    let trigger = "card_lost";
    const lost = h("button", { class: "choice", "aria-pressed": "true", onclick: () => pick("card_lost") }, "😟 My card is lost");
    const stolen = h("button", { class: "choice", "aria-pressed": "false", onclick: () => pick("card_stolen") }, "🚨 My card was stolen");
    function pick(t) { trigger = t; lost.setAttribute("aria-pressed", t === "card_lost"); stolen.setAttribute("aria-pressed", t === "card_stolen"); }
    const words = typed(h("textarea", { class: "field", rows: "3", placeholder: "e.g. I lost my Wise card on the bus", "aria-label": "What happened, in your own words" }));
    const go = h("button", { class: "btn danger", onclick: async () => {
      if (!words.value.trim()) { words.focus(); return; }
      go.disabled = true;
      try { render(await call("POST", "/rescue/start", { user_id: USER, trigger, text: words.value.trim() })); }
      catch (e) { box.prepend(h("div", { class: "error" }, errorText(e))); go.disabled = false; }
    } }, "Start the rescue");
    box.replaceChildren(h("div", { class: "card" },
      h("p", { class: "muted" }, "Lifeline walks you through it, one step at a time. Nothing moves until you confirm."),
      lost, stolen, h("h2", { style: "margin-top:10px" }, "What happened?"), words,
      h("p", { class: "muted small" }, "Type this yourself. Pasting is off here, because only your own words can move a rescue."), go));
  }
  function render(r) {
    const st = r.rescue?.state_after;
    const at = Math.max(0, ORDER.indexOf(st));
    const card = h("div", { class: "card" },
      h("div", { class: "steps", "aria-hidden": "true" }, ORDER.map((_, i) => h("span", { class: i <= at ? "on" : "" }))),
      h("p", { class: "muted small" }, `Step: ${STEP_NAMES[st] ?? "Starting"}`));
    replyNodes(r, (n) => card.append(n), render).forEach((n) => card.append(n));
    const doNow = r.rescue?.do_now;
    if (doNow === "answer_identity_question") {
      // The answer is sent once and not kept anywhere in the app.
      const ans = typed(h("input", { class: "field", type: "text", autocomplete: "off", "aria-label": "Your answer" }));
      card.append(ans, h("button", { class: "btn", onclick: async (ev) => { ev.currentTarget.disabled = true; await step({ text: ans.value }); } }, "Send answer"));
    } else if (doNow === "choose_card") {
      card.append(h("h2", {}, "Which card?"), ...(r.rescue.card_names || []).map((n) => h("button", { class: "choice", onclick: () => step({ text: n }) }, "💳 ", n)));
    } else if (doNow === "confirm_freeze" || doNow === "confirm_transfer_or_skip") {
      const token = r.confirmation?.confirmation_token;
      const row = h("div", { class: "row" });
      if (doNow === "confirm_transfer_or_skip") row.append(h("button", { class: "btn secondary", onclick: () => step({ text: "" }) }, "Continue without money"));
      row.append(h("button", { class: "btn", onclick: (ev) => { ev.currentTarget.disabled = true; step({ text: "", confirmation_token: token }); } }, doNow === "confirm_freeze" ? "Freeze my card" : "Send me the money"));
      card.append(row);
    } else if (doNow === "locked") {
      card.append(h("div", { class: "error" }, "This rescue is locked after three wrong answers, to protect you. Contact your bank directly."));
    } else if (doNow === "done") {
      card.append(h("button", { class: "btn secondary", onclick: () => go("activity") }, "See what happened"));
    }
    box.replaceChildren(card);
  }
  async function step(body) {
    try { render(await call("POST", "/rescue/step", { user_id: USER, ...body })); }
    catch (e) { box.prepend(h("div", { class: "error" }, errorText(e))); }
  }
}
function typed(el) { el.addEventListener("paste", (ev) => ev.preventDefault()); el.addEventListener("drop", (ev) => ev.preventDefault()); return el; }

// ---------- Activity ----------
// Ledger entries in plain words. Only what the entries say; anything else stays in the technical view.
function friendly(entries) {
  const out = [];
  const tag = (o, group) => (o.group = group, o);
  for (const e of entries) {
    const p = e.payload || {};
    if (e.kind === "receipt" && p.receipt) {
      const rc = p.receipt;
      out.push(tag({ emoji: rc.status === "completed" ? "✅" : "⏳", what: `${money(rc.amount, rc.currency)} via ${rc.rail}`, sub: `${rc.status.replace("_", " ")}${rc.simulated ? " · simulated" : ""}`, ts: e.ts }, "pay"));
    } else if (e.kind === "decision" && p.decision && p.decision.allowed === false) {
      out.push(tag({ emoji: "⛔", what: `Blocked: ${(p.action?.type || "a request").replace("_", " ")}`, sub: `rules ${(p.decision.rule_ids || []).join(", ")}`, ts: e.ts }, "blocked"));
    } else if (e.kind === "note" && p.kind === "family_notice") {
      out.push(tag({ emoji: "👪", what: "Family notice written", sub: "for the app to deliver", ts: e.ts }, "rescue"));
    } else if (e.kind === "note" && /^rescue_/.test(p.kind || "")) {
      out.push(tag({ emoji: "🛟", what: `Rescue: ${p.kind.replace("rescue_", "").replace(/_/g, " ")}`, sub: "", ts: e.ts }, "rescue"));
    } else if (e.kind === "execution" && p.result?.freeze) {
      out.push(tag({ emoji: "🧊", what: "Card freeze", sub: p.result.freeze.status.replace("_", " "), ts: e.ts }, "rescue"));
    }
  }
  return out.reverse();
}
function row(it) { return h("li", {}, h("span", { class: "emoji", "aria-hidden": "true" }, it.emoji), h("div", {}, h("div", { class: "what" }, it.what), h("div", { class: "muted small" }, [it.sub, when(it.ts)].filter(Boolean).join(" · ")))); }
function setBadge(el, v) {
  const ok = v.first_broken_seq === null || v.first_broken_seq === undefined;
  el.className = ok ? "badge" : "badge warn";
  el.textContent = ok ? "🔒 Verified: this history can't be secretly changed" : `⚠️ Entry ${v.first_broken_seq} was changed. Payments are paused.`;
}
async function activity() {
  const list = h("ul", { class: "list" }, h("li", {}, h("span", { class: "muted" }, "Loading…")));
  const badge = h("span", { class: "badge" }, "🔒 Checking…");
  const tech = h("div", { hidden: true });
  const FILTERS = [["all", "All"], ["pay", "Payments"], ["blocked", "Blocked"], ["rescue", "Rescue"]];
  let items = [];
  const filters = h("div", { class: "filters", role: "group", "aria-label": "Show" });
  function draw(which) {
    filters.replaceChildren(...FILTERS.map(([k, label]) => h("button", { "aria-pressed": k === which ? "true" : "false", onclick: () => draw(k) }, label)));
    const shown = which === "all" ? items : items.filter((i) => i.group === which);
    list.replaceChildren(...(shown.length ? shown.map(row) : [h("li", {}, h("span", { class: "muted" }, which === "all" ? "Nothing yet. Payments, blocks and rescues show here." : "Nothing here yet."))]));
  }
  view.append(h("h1", {}, "Activity"), h("p", {}, badge), filters, h("section", { class: "card" }, list),
    h("button", { class: "link", onclick: () => { tech.hidden = !tech.hidden; } }, "Advanced: technical ledger"), tech);
  try {
    const [entries, verify] = await Promise.all([call("GET", `/ledger/${USER}`), call("GET", `/ledger/${USER}/verify`)]);
    items = friendly(entries);
    draw("all");
    setBadge(badge, verify);
    tech.replaceChildren(h("section", { class: "card" }, h("p", { class: "muted small" }, `${entries.length} entries, each chained to the one before by its hash.`),
      h("ul", { class: "list" }, entries.slice().reverse().map((e) => h("li", {}, h("span", { class: "tech" }, `#${e.seq} ${e.kind}${e.payload?.kind ? ": " + e.payload.kind : ""} · ${e.hash.slice(0, 10)}…`))))));
  } catch (e) { list.replaceChildren(h("li", {}, h("span", { class: "muted" }, errorText(e)))); badge.remove(); }
}

// ---------- Help ----------
function help() {
  const faq = [
    ["What does Lifeline do?", "It helps you move money across borders within limits you set, and protects you from scams and a lost card."],
    ["What will it never do?", "It never holds your money, never gives investment advice, never changes your limits in chat, and never asks for your identity documents."],
    ["Why is a message I received kept separate?", "Only your own words can start a payment. A message someone sent you, like a fake bank email, is read as information and can never move money, even if it asks to."],
    ["What happens before money moves?", "Lifeline shows you exactly what will be sent, to whom, and every route with its fee. Nothing moves until you tap Confirm, and that confirmation expires after five minutes."],
    ["I lost my card. What now?", "Tap Lost card. Lifeline checks it's you, freezes the card or links you to your bank's app, switches to your backup card and can send emergency money to your own account."],
    ["Is this real money?", "No. This is a demo with one demo student. Every route is simulated or a stand in, and there is no sign in yet."],
  ];
  view.append(h("h1", {}, "Help"), h("section", { class: "card" }, faq.map(([q, a]) => h("details", { class: "faq" }, h("summary", {}, q), h("p", {}, a)))));
}

// ---------- Welcome and sign in ----------
// Designed in full, but the API has no sign in (docs/api.md, "Security"; self assessment, open item 37), so only
// "Try the demo" works and every sign in option says Coming soon. Nothing is remembered: a reload shows this again.
const SLIDES = [
  { emoji: "🌏", title: "Move money home and away", text: "Pay rent abroad or get money from family, within limits you set." },
  { emoji: "🛡️", title: "Stay safe from scams", text: "Paste a message you're unsure about. Lifeline reads it, and it can never move your money." },
  { emoji: "🛟", title: "Lost your card?", text: "Freeze it, switch to your backup and get emergency money, step by step." },
];
function welcome() {
  let at = 0;
  const slide = h("div", { class: "card slide", "aria-live": "polite" });
  const dots = h("div", { class: "dots", role: "group", "aria-label": "Intro slides" });
  function show(i) {
    at = (i + SLIDES.length) % SLIDES.length;
    const s = SLIDES[at];
    slide.replaceChildren(h("span", { class: "emoji", "aria-hidden": "true" }, s.emoji), h("h2", {}, s.title), h("p", { class: "muted" }, s.text));
    dots.replaceChildren(...SLIDES.map((_, j) => h("button", { "aria-label": `Slide ${j + 1}`, "aria-current": j === at ? "true" : "false", onclick: () => show(j) })));
  }
  let startX = null;
  slide.addEventListener("touchstart", (e) => { startX = e.touches[0].clientX; }, { passive: true });
  slide.addEventListener("touchend", (e) => { if (startX === null) return; const dx = e.changedTouches[0].clientX - startX; if (Math.abs(dx) > 40) show(at + (dx < 0 ? 1 : -1)); startX = null; });
  show(0);
  const soon = (cls, icon, label) => h("div", { class: `sso ${cls}`, role: "button", "aria-disabled": "true", title: "Sign in is not built yet" }, h("span", { "aria-hidden": "true" }, icon), h("span", { class: "lbl" }, label), h("span", { class: "soon" }, "Coming soon"));
  view.append(
    h("div", { class: "hero" },
      h("div", { class: "orb", role: "img", "aria-label": "The Lifeline heartbeat" }),
      h("h1", {}, "Your money's ", h("em", {}, "lifeline"), " abroad"), h("p", {}, "Move money safely. Stay safe from scams. Get help when a card is lost.")),
    slide, dots,
    h("div", { class: "signin-stack" },
      soon("faceid", "🙂", "Continue with Face ID"),
      soon("apple", "", "Continue with Apple"),
      soon("google", "G", "Continue with Google"),
      h("div", { class: "divider" }, "or"),
      h("button", { class: "btn", onclick: () => go("hello") }, "Try the demo"),
      h("p", { class: "fine" }, "Sign in isn't built yet, so the demo runs as one demo student. No real money moves.")),
  );
  // The heartbeat, a fixed drawing written here, never server text.
  view.querySelector(".orb").innerHTML = `<svg viewBox="0 0 48 24" aria-hidden="true"><path class="trace" d="${PULSE}"/></svg>`;
}

// The Lifeline logo's line, as on a heart monitor.
const PULSE = "M1 12h12l4-9 6 18 5-14 3 5h16";

// After Try the demo: who you are in this demo and what your safety net holds. Every line is the demo plan in
// fixtures/demo_user.yaml as docs/api.md, "Rescue", states it; nothing here is asked of the student or stored.
function hello() {
  const plan = [
    ["💳", "Main card", "Wise debit card"],
    ["🛟", "Backup card", "Revolut card, from a different provider"],
    ["🔐", "Safety question", "Set before you left, checked if a card is lost"],
    ["💸", "Emergency money", "300 SGD to your own Singapore account, after you confirm"],
  ];
  view.append(
    h("div", { class: "hello" }, h("span", { class: "wave", "aria-hidden": "true" }, "👋"),
      h("h1", {}, "Welcome to Lifeline"), h("p", {}, "This demo runs as one student in Singapore. Here's the safety net already set up.")),
    h("section", { class: "card" }, h("h2", {}, "Your safety net"),
      h("ul", { class: "list" }, plan.map(([e, what, sub]) => h("li", {}, h("span", { class: "emoji", "aria-hidden": "true" }, e), h("div", {}, h("div", { class: "what" }, what), h("div", { class: "muted small" }, sub)))))),
    h("p", { class: "muted small", style: "text-align:center" }, "Setting up your own plan is coming soon."),
    h("div", { class: "go-pill" }, h("button", { class: "btn", onclick: () => go("home") }, "Get started"),
      h("span", { class: "arrows", "aria-hidden": "true" }, h("span", {}, "›"), h("span", {}, "›"), h("span", {}, "›"))),
  );
}

// 404: the line goes flat.
function lost() {
  const flat = "M0 60h70l10-30 14 60 12-44 8 14h46l10-30 14 60 12-44 8 14h40l8-16 10 30 8-14h12 L520 60";
  const box = h("div", { class: "monitor", "aria-hidden": "true" });
  box.innerHTML = `<svg viewBox="0 0 520 120" preserveAspectRatio="none"><path class="trace" d="${flat}"/><circle class="dot" cx="508" cy="60" r="5"/></svg>`;
  view.append(h("div", { class: "lost" }, box,
    h("p", { class: "code" }, "ERROR 404"),
    h("h1", {}, "This page flatlined."),
    h("p", {}, "We checked for a pulse, but the page you're looking for isn't here. Your money is fine."),
    h("button", { class: "btn", onclick: () => go("home") }, "Back to Home")));
}

// A known screen in the address, such as #chat, opens it; anything else is the 404.
const start = location.hash.slice(1);
go(start === "" ? "welcome" : start in screens ? start : "lost");
