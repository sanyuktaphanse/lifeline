// The Me page, opened from the header: the trip, the safety net with Change, how routes are chosen, the checks a
// provider may run for this trip, and sign in, which is not built. Nothing on this page is sent to the server
// except a check the student taps, because POST /precheck writes an entry to the ledger (docs/api.md).
import { el, errorText, label } from "../dom.js";
import { t } from "../i18n.js";
import { countryName } from "../countries.js";
import { SAMPLE_PLAN, cardChoices, planContact } from "../onboarding.js";
import { precheckFor } from "../tailoring.js";

function row(ctx, key, ...value) {
  return [label(ctx, "dt", key), el("dd", {}, ...value)];
}

// The plan as facts, for the Me page and for the onboarding's summary. With no plan it is the sample plan.
export function planFacts(ctx, plan) {
  const lang = ctx.lang();
  if (!plan) {
    return el(
      "dl",
      { class: "facts" },
      row(ctx, "me_card", SAMPLE_PLAN.cards[0]),
      row(ctx, "me_backup", SAMPLE_PLAN.cards[1]),
      row(ctx, "me_question", label(ctx, "span", "safety_q_pass")),
      row(ctx, "me_contact", t(lang, "me_contact_line", { name: SAMPLE_PLAN.contact.name, channel: t(lang, `channel_${SAMPLE_PLAN.contact.channel}`) })),
      row(ctx, "me_money", t(lang, "onb_money_amount", { amount: SAMPLE_PLAN.money, currency: SAMPLE_PLAN.currency })),
    );
  }
  const card = cardChoices(null).find((choice) => choice.id === plan.card);
  const contact = planContact(plan.contact);
  const onPage = [plan.contact.phone, plan.contact.email].map((value) => value?.trim()).filter(Boolean);
  return el(
    "dl",
    { class: "facts" },
    row(ctx, "me_card", card.key ? label(ctx, "span", card.key) : card.name),
    row(ctx, "me_backup", label(ctx, "span", plan.backup ? "onb_yes" : "onb_no")),
    row(ctx, "me_question", label(ctx, "span", plan.question), " ", label(ctx, "span", "me_question_set", null, { class: "hint" })),
    row(
      ctx,
      "me_contact",
      t(lang, "me_contact_line", { name: contact.name, channel: t(lang, `channel_${contact.channel}`) }),
      onPage.length ? el("div", { class: "hint" }, t(lang, "me_on_device", { details: onPage.join(", ") })) : null,
    ),
    row(ctx, "me_money", plan.money === "none" ? label(ctx, "span", "onb_money_none") : t(lang, "onb_money_amount", { amount: plan.money, currency: SAMPLE_PLAN.currency })),
  );
}

export function meView(ctx, root, { onChange, onClose }) {
  // The answers to checks already tapped, kept so a language change does not ask the server again.
  const results = new Map();

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
    const sample = !ctx.profile.plan;
    return el(
      "section",
      { class: "card", id: "me-net" },
      el("h3", {}, label(ctx, "span", "me_net"), " ", sample ? label(ctx, "span", "me_sample", null, { class: "badge" }) : null),
      sample ? label(ctx, "p", "me_sample_note", null, { class: "hint" }) : null,
      planFacts(ctx, ctx.profile.plan),
      // The sample plan already shows its question; a plan set here does not reach the rescue, so it says so.
      sample ? null : label(ctx, "p", "onb_rescue_note", null, { class: "hint" }),
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

  return { shown: draw, relang: draw };
}
