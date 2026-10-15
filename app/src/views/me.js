// The Me page, opened from the header: the trip, the safety net with Change, how routes are chosen, the checks a
// provider may run for this trip, and sign in, which is not built. Nothing on this page is sent to the server
// except a check the student taps, because POST /precheck writes an entry to the ledger (docs/api.md). The plan on
// file is read from GET /ledger, a read.
import { el, errorText, label } from "../dom.js";
import { t } from "../i18n.js";
import { countryName } from "../countries.js";
import { precheckFor } from "../tailoring.js";
import { CASH_CHOICES } from "../onboarding.js";

// One field of the plan in plain words, for Me and for "On file" in the onboarding steps.
export function fieldText(lang, plan, field) {
  const cardName = (id) => plan.cards.find((card) => card.instrument_id === id)?.name ?? id ?? t(lang, "me_none");
  const named = (key, fallback) => (t(lang, key) === key ? fallback : t(lang, key));
  switch (field) {
    case "primary_instrument":
    case "backup_instrument":
      return cardName(plan[field]);
    case "backup_route":
      return plan.backup_route ? named(`rail_${plan.backup_route}`, plan.backup_route) : t(lang, "me_none");
    case "wallet_token_present":
      return t(lang, plan.wallet_token_present ? "me_yes" : "me_no");
    case "cash_plan":
    {
      // A cash plan the steps offer is named in words, with its entry id; any other is listed by its ids.
      const choice = CASH_CHOICES.find((item) => JSON.stringify(item.ids) === JSON.stringify(plan.cash_plan));
      return choice ? t(lang, `onb_cash_${choice.id}`) : plan.cash_plan.join(", ");
    }
    case "channel":
      return named(`channel_${plan.trusted_contact.channel}`, plan.trusted_contact.channel);
    default:
      return "";
  }
}

// The plan on file as facts. Every value comes from the plan the server holds: the sample plan with the updates
// the ledger records. The answer to the safety question is never shown.
function planFacts(ctx, plan) {
  const lang = ctx.lang();
  const row = (key, value) => [label(ctx, "dt", key), el("dd", {}, value)];
  return el(
    "dl",
    { class: "facts" },
    row("me_card", fieldText(lang, plan, "primary_instrument")),
    row("me_backup_card", fieldText(lang, plan, "backup_instrument")),
    row("me_backup_route", fieldText(lang, plan, "backup_route")),
    row("me_wallet", fieldText(lang, plan, "wallet_token_present")),
    row("me_cash", fieldText(lang, plan, "cash_plan")),
    row("me_contact", t(lang, "me_contact_line", { name: plan.trusted_contact.name, channel: fieldText(lang, plan, "channel") })),
    row("me_money", `${plan.emergency_allowance} ${plan.currency}`),
    row("me_question", t(lang, "sample_question")),
  );
}

export function meView(ctx, root, { onChange, onClose }) {
  // The answers to checks already tapped, kept so a language change does not ask the server again.
  const results = new Map();
  let plan = null;
  let failure = null;

  function tripSection() {
    const trip = ctx.profile.trip;
    const lang = ctx.lang();
    return el(
      "section",
      { class: "card", id: "me-trip" },
      label(ctx, "h3", "me_trip"),
      trip
        ? el("p", {}, t(lang, "me_trip_line", { purpose: t(lang, `purpose_${trip.purpose}`), home: countryName(trip.home, lang), study: countryName(trip.study, lang) }))
        : label(ctx, "p", "me_no_trip", null, { class: "hint" }),
      label(ctx, "button", "me_change", null, { type: "button", class: "btn", id: "me-change-trip", onclick: () => onChange("trip") }),
    );
  }

  function netSection() {
    const body = failure ? el("p", { class: "error", role: "alert" }, errorText(ctx, failure)) : plan ? planFacts(ctx, plan) : null;
    return el(
      "section",
      { class: "card", id: "me-net" },
      el("h3", {}, label(ctx, "span", "me_net"), " ", label(ctx, "span", "me_sample", null, { class: "badge" })),
      label(ctx, "p", "me_sample_note", null, { class: "hint" }),
      body,
      label(ctx, "button", "me_change", null, { type: "button", class: "btn", id: "me-change-net", onclick: () => onChange("plan") }),
    );
  }

  function checkResult(ctx, result) {
    return [
      result.documents_likely?.length ? [label(ctx, "h4", "me_check_documents"), el("ul", {}, result.documents_likely.map((item) => el("li", {}, item)))] : null,
      result.review_triggers?.length ? [label(ctx, "h4", "me_check_triggers"), el("ul", {}, result.review_triggers.map((item) => el("li", {}, item)))] : null,
      result.ready === false ? label(ctx, "p", "me_check_not_ready", null, { class: "error" }) : null,
      result.rule_ids?.length ? label(ctx, "p", "me_check_sources", { ids: result.rule_ids.join(", ") }, { class: "hint mono" }) : null,
    ];
  }

  function checksSection() {
    const checks = precheckFor(ctx.profile.trip);
    if (!checks.length) return el("section", { class: "card", id: "me-checks" }, label(ctx, "h3", "me_checks"), label(ctx, "p", "me_check_none", null, { class: "hint" }));
    return el(
      "section",
      { class: "card", id: "me-checks" },
      label(ctx, "h3", "me_checks"),
      label(ctx, "p", "me_check_intro", null, { class: "hint" }),
      checks.map((check) => {
        const out = el("div", { class: "me-check-result", "data-kind": check.action_kind, "aria-live": "polite" });
        if (results.has(check.action_kind)) out.replaceChildren(...checkResult(ctx, results.get(check.action_kind)).flat(2).filter(Boolean));
        const button = label(ctx, "button", "me_check_button", { what: t(ctx.lang(), `check_${check.action_kind}`) }, { type: "button", class: "btn me-check", "data-kind": check.action_kind });
        button.addEventListener("click", async () => {
          button.disabled = true;
          out.replaceChildren();
          try {
            const result = await ctx.api.precheck({ user_id: ctx.userId, ...check });
            results.set(check.action_kind, result);
            out.replaceChildren(...checkResult(ctx, result).flat(2).filter(Boolean));
          } catch (failure) {
            out.replaceChildren(el("p", { class: "error", role: "alert" }, errorText(ctx, failure)));
          } finally {
            button.disabled = false;
          }
        });
        return el("div", { class: "me-check-block" }, button, out);
      }),
    );
  }

  function draw() {
    root.replaceChildren(
      label(ctx, "h2", "me_title"),
      tripSection(),
      netSection(),
      el("section", { class: "card", id: "me-routes" }, label(ctx, "h3", "me_routes"), label(ctx, "p", "me_route_rule")),
      checksSection(),
      el("section", { class: "card", id: "me-signin" }, el("p", {}, label(ctx, "span", "me_coming_soon", null, { class: "badge" }), " ", label(ctx, "span", "me_signin"))),
      label(ctx, "button", "me_close", null, { type: "button", class: "btn", id: "me-close", onclick: onClose }),
    );
  }

  async function load() {
    draw();
    try {
      plan = await ctx.loadPlan();
      failure = null;
    } catch (error) {
      failure = error;
    }
    draw();
  }

  return { shown: load, relang: draw };
}
