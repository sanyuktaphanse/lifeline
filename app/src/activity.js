// The ledger in plain words, the way a banking app lists what happened. Each line says only what its entry says;
// every entry, these and the rest, stays under Advanced. A receipt finds what it paid for through the proposal
// with the same idempotency key. Nothing here writes: the entries come from GET /ledger/{user_id}.

// fixture: the payees of the demo mandates (fixtures/demo_user.yaml and fixtures/demo_parent.yaml), by plain name.
const PAYEES = ["landlord_sp", "self_sg", "student_001"];
export const payeeKey = (payee) => (PAYEES.includes(payee) ? `payee_${payee}` : null);

export function friendlyEntries(entries) {
  const actions = new Map();
  for (const entry of entries) {
    const action = entry.payload?.action;
    if (action?.idempotency_key) actions.set(action.idempotency_key, action);
  }
  const rows = [];
  const add = (entry, key, values = {}, extra = {}) => rows.push({ seq: entry.seq, ts: entry.ts, key, values, ...extra });
  for (const entry of entries) {
    const payload = entry.payload ?? {};
    if (entry.kind === "receipt" && payload.receipt) {
      const receipt = payload.receipt;
      const values = { amount: receipt.amount, currency: receipt.currency, payee: actions.get(receipt.idempotency_key)?.payee_id ?? null };
      const done = receipt.status === "completed";
      add(entry, done ? "act_sent" : "act_sent_status", done ? values : { ...values, status: receipt.status }, { simulated: receipt.simulated === true, tone: done ? "ok" : null });
    } else if (entry.kind === "decision" && payload.decision?.allowed === false) {
      // R01 is the engine's rule that only the student's own turn can start an action.
      if ((payload.decision.rule_ids ?? []).includes("R01")) add(entry, "act_refused_paste", {}, { tone: "bad" });
      else add(entry, "act_refused", { type: actions.get(payload.idempotency_key)?.type ?? null }, { tone: "bad" });
    } else if (entry.kind === "execution" && payload.result?.freeze) {
      const status = payload.result.freeze.status;
      if (status === "done") add(entry, "act_frozen", {}, { tone: "ok" });
      else add(entry, "act_freeze_status", { status });
    } else if (entry.kind === "execution" && payload.action?.type === "precheck") {
      add(entry, "act_precheck");
    } else if (entry.kind === "note" && payload.kind === "rescue_started") {
      add(entry, "act_rescue_started");
    } else if (entry.kind === "note" && payload.kind === "rescue_replacement") {
      add(entry, "act_replacement");
    } else if (entry.kind === "note" && payload.kind === "family_notice") {
      add(entry, "act_family_told", { name: payload.to?.name ?? null, channel: payload.to?.channel ?? null });
    }
  }
  return rows.reverse();
}

const LOCALES = { en: "en-GB", pt: "pt-BR", zh: "zh-CN" };

function dayStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

// Groups rows that are already newest first under Today, Yesterday or the date, by the device's own time zone.
export function groupByDay(rows, now, lang) {
  const today = dayStart(now);
  const groups = [];
  for (const row of rows) {
    const when = new Date(row.ts);
    const days = Math.round((today - dayStart(when)) / 86400000);
    const head =
      days === 0 ? { key: "activity_today" } : days === 1 ? { key: "activity_yesterday" } : { date: when.toLocaleDateString(LOCALES[lang] ?? lang, { day: "numeric", month: "short" }) };
    const last = groups.at(-1);
    if (last && last.key === head.key && last.date === head.date) last.rows.push(row);
    else groups.push({ ...head, rows: [row] });
  }
  return groups;
}
