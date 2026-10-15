// Activity: what happened, in plain words grouped by day, from GET /ledger/{user_id}. Every entry, these and the
// rest, is under Advanced, where the ledger screen shows the chain check and each entry's payload and hashes.
import { el, errorText } from "../dom.js";
import { t } from "../i18n.js";
import { friendlyEntries, groupByDay, payeeKey } from "../activity.js";
import { ledgerView } from "./ledger.js";

function typeLabel(lang, type) {
  const key = `type_${type}`;
  const text = t(lang, key);
  return text === key ? type ?? "" : text;
}

function rowText(lang, row) {
  const values = { ...row.values };
  if ("payee" in values) values.payee = values.payee ? (payeeKey(values.payee) ? t(lang, payeeKey(values.payee)) : values.payee) : t(lang, "payee_unknown");
  if ("type" in values) values.type = typeLabel(lang, values.type);
  if ("channel" in values && values.channel) {
    const key = `channel_${values.channel}`;
    values.channel = t(lang, key) === key ? values.channel : t(lang, key);
  }
  return t(lang, row.key, values);
}

export function activityView(ctx, root) {
  const list = el("div", { id: "activity-list", "aria-live": "polite" });
  const ledgerRoot = el("div", { class: "activity-ledger" });
  const advanced = el("details", { id: "activity-advanced" }, el("summary", { "data-i18n": "activity_advanced" }, t(ctx.lang(), "activity_advanced")), ledgerRoot);
  const ledger = ledgerView(ctx, ledgerRoot);
  let rows = null;
  let failure = null;

  advanced.addEventListener("toggle", () => {
    if (advanced.open) ledger.shown();
  });

  function draw() {
    const lang = ctx.lang();
    if (failure) return list.replaceChildren(el("p", { class: "error", role: "alert" }, errorText(ctx, failure)));
    if (!rows) return list.replaceChildren();
    if (!rows.length) return list.replaceChildren(el("p", { class: "hint" }, t(lang, "activity_empty")));
    list.replaceChildren(
      ...groupByDay(rows, new Date(), lang).map((group) =>
        el(
          "section",
          { class: "day" },
          el("h3", {}, group.key ? t(lang, group.key) : group.date),
          el(
            "ul",
            { class: "card act-list" },
            group.rows.map((row) =>
              el(
                "li",
                { class: `act-row ${row.tone ? `act-${row.tone}` : ""}`, "data-seq": row.seq },
                el("span", {}, rowText(lang, row)),
                row.simulated ? el("span", { class: "badge" }, t(lang, "route_simulated")) : null,
                el("div", { class: "hint" }, `${new Date(row.ts).toLocaleTimeString({ en: "en-GB", pt: "pt-BR", zh: "zh-CN" }[lang] ?? lang, { hour: "2-digit", minute: "2-digit" })} · ${t(lang, "activity_seq", { seq: row.seq })}`),
              ),
            ),
          ),
        ),
      ),
    );
  }

  async function load() {
    try {
      rows = friendlyEntries(await ctx.api.ledger(ctx.userId));
      failure = null;
    } catch (error) {
      failure = error;
    }
    draw();
    if (advanced.open) ledger.shown();
  }

  root.replaceChildren(el("h2", { "data-i18n": "tab_activity" }, t(ctx.lang(), "tab_activity")), el("p", { class: "intro", "data-i18n": "activity_intro" }, t(ctx.lang(), "activity_intro")), list, advanced);
  return { shown: load, relang: draw };
}
