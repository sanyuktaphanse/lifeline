// The onboarding after the welcome: three questions about the trip, kept in page memory only, then the safety net.
// Four of its steps are the fields update_plan changes at tier 1; they end in one message the student puts in the
// chat box, reads and sends through /chat, where the engine checks it and the ledger records the change. The trusted
// contact, the emergency money and the safety question are read only, because chat cannot change them, so nothing is
// asked for them. What is on file is read from GET /ledger, a read. Skip keeps the plan as it is on file.
// Me opens the same screens again with "trip" or "plan".
import { el, errorText, label } from "../dom.js";
import { t } from "../i18n.js";
import { countryGroups, countryName, hasRules } from "../countries.js";
import { fieldText } from "./me.js";
import {
  CASH_CHOICES, PLAN_STEPS, PURPOSES, READ_ONLY_STEPS, ROUTE_CHOICES, backupChoices, composeMessage, planChanges, tripReady,
} from "../onboarding.js";

export function onboardingView(ctx, root, onFinish) {
  let mode = "all";
  let page = "trip";
  let index = 0;
  let trip = {};
  let onFile = null;
  let draft = {};
  let failure = null;

  function start(nextMode) {
    mode = nextMode;
    trip = { ...(ctx.profile.trip ?? {}) };
    index = 0;
    if (mode === "plan") toSteps();
    else {
      page = "trip";
      draw();
    }
  }

  // The plan on file, read again each time the steps open, so a change sent in chat shows as on file.
  async function toSteps() {
    page = "step";
    root.replaceChildren();
    try {
      onFile = await ctx.loadPlan();
      failure = null;
    } catch (error) {
      failure = error;
    }
    draft = onFile ? { backup_instrument: onFile.backup_instrument, backup_route: onFile.backup_route, wallet_token_present: onFile.wallet_token_present, cash_plan: [...onFile.cash_plan] } : {};
    draw();
  }

  // Skip leaves the plan as it was: the sample plan, unless one was set before. From Me it changes nothing.
  function skip() {
    onFinish(mode === "all" ? "chat" : "me");
  }

  function draw() {
    if (page !== "trip" && failure) {
      root.replaceChildren(el("p", { class: "error", role: "alert" }, errorText(ctx, failure)), skipRow());
      return;
    }
    root.replaceChildren(page === "trip" ? tripPage() : page === "step" ? stepPage() : messagePage());
  }

  function skipRow() {
    return el(
      "div",
      { class: "onb-skip" },
      label(ctx, "button", "onb_skip", null, { type: "button", class: "btn", id: "onb-skip", onclick: skip }),
      mode === "all" ? label(ctx, "p", "onb_skip_note", null, { class: "hint", id: "onb-skip-note" }) : null,
    );
  }

  function tripPage() {
    const go = label(ctx, "button", "onb_continue", null, { type: "button", class: "btn btn-primary", id: "onb-continue" });
    const ready = () => {
      go.disabled = !tripReady(trip);
    };
    go.addEventListener("click", () => {
      if (!tripReady(trip)) return;
      ctx.profile.trip = { home: trip.home, study: trip.study, purpose: trip.purpose };
      if (mode === "trip") {
        onFinish("me");
        return;
      }
      index = 0;
      toSteps();
    });
    const purposes = radios("onb-purpose", PURPOSES.map((id) => ({ value: id, key: `purpose_${id}` })), trip.purpose, (value) => {
      trip.purpose = value;
      ready();
    });
    ready();
    return el(
      "div",
      { class: "onb" },
      label(ctx, "h2", "onb_trip_title"),
      label(ctx, "p", "onb_trip_intro", null, { class: "intro" }),
      countryField("home", "onb_home", ready),
      countryField("study", "onb_study", ready),
      el("fieldset", { class: "onb-choices" }, label(ctx, "legend", "onb_purpose"), purposes),
      go,
      skipRow(),
    );
  }

  // A native select keeps the keyboard, the screen reader and the phone's own picker. The four countries with
  // rules on file come first in their own group; the group heading is bold everywhere and the names are bold
  // wherever the browser draws option styles.
  function countryField(which, key, ready) {
    const lang = ctx.lang();
    const groups = countryGroups(lang);
    const id = `onb-${which}`;
    const note = el("p", { class: "hint", id: `${id}-note`, "aria-live": "polite" });
    const select = el(
      "select",
      { id },
      el("option", { value: "" }, t(lang, "onb_choose_country")),
      el("optgroup", { label: t(lang, "onb_group_on_file"), class: "on-file" }, groups.onFile.map((item) => el("option", { value: item.code, class: "on-file" }, item.label))),
      el("optgroup", { label: t(lang, "onb_group_others") }, groups.others.map((item) => el("option", { value: item.code }, item.label))),
    );
    const showNote = () => {
      const code = trip[which];
      note.textContent = code && !hasRules(code) ? t(ctx.lang(), "onb_no_rules", { place: countryName(code, ctx.lang()) }) : "";
    };
    select.value = trip[which] ?? "";
    select.addEventListener("change", () => {
      trip[which] = select.value || null;
      showNote();
      ready();
    });
    showNote();
    return el("div", { class: "field" }, label(ctx, "label", key, null, { for: id }), select, note);
  }

  function radios(name, options, current, onPick) {
    return el(
      "div",
      { class: "onb-options" },
      options.map((option) => {
        const input = el("input", { type: "radio", name, value: option.value, checked: option.value === current });
        input.addEventListener("change", () => onPick(option.value));
        return el("label", { class: "onb-option" }, input, option.key ? label(ctx, "span", option.key, option.values) : el("span", {}, option.text));
      }),
    );
  }

  function onFileLine(field) {
    return el("p", { class: "hint onb-on-file" }, t(ctx.lang(), "onb_on_file", { value: fieldText(ctx.lang(), onFile, field) }));
  }

  function stepBody(step) {
    const lang = ctx.lang();
    if (step === "backup_card") {
      const main = onFile.cards.find((card) => card.instrument_id === onFile.primary_instrument)?.name ?? onFile.primary_instrument;
      return [
        label(ctx, "h3", "onb_backup_card_q"),
        onFileLine("backup_instrument"),
        el("p", { class: "hint" }, t(lang, "onb_backup_card_hint", { main })),
        radios("onb-backup_card", backupChoices(onFile).map((card) => ({ value: card.instrument_id, text: card.name })), draft.backup_instrument, (value) => {
          draft.backup_instrument = value;
        }),
      ];
    }
    if (step === "backup_route") {
      return [
        label(ctx, "h3", "onb_backup_route_q"),
        onFileLine("backup_route"),
        label(ctx, "p", "onb_backup_route_hint", null, { class: "hint" }),
        radios("onb-backup_route", ROUTE_CHOICES.map((rail) => ({ value: rail, key: `rail_${rail}` })), draft.backup_route, (value) => {
          draft.backup_route = value;
        }),
      ];
    }
    if (step === "wallet") {
      return [
        label(ctx, "h3", "onb_wallet_q"),
        onFileLine("wallet_token_present"),
        radios("onb-wallet", [{ value: "yes", key: "onb_wallet_yes" }, { value: "no", key: "onb_wallet_no" }], draft.wallet_token_present ? "yes" : "no", (value) => {
          draft.wallet_token_present = value === "yes";
        }),
      ];
    }
    if (step === "cash_plan") {
      const current = CASH_CHOICES.find((choice) => JSON.stringify(choice.ids) === JSON.stringify(draft.cash_plan))?.id ?? null;
      return [
        label(ctx, "h3", "onb_cash_q"),
        onFileLine("cash_plan"),
        radios("onb-cash_plan", CASH_CHOICES.map((choice) => ({ value: choice.id, key: `onb_cash_${choice.id}` })), current, (value) => {
          draft.cash_plan = [...CASH_CHOICES.find((choice) => choice.id === value).ids];
        }),
      ];
    }
    // Read only: what is on file and why chat cannot change it. No field, so nothing is collected.
    if (step === "contact") {
      const contact = onFile.trusted_contact;
      return [
        label(ctx, "h3", "onb_contact_title"),
        el("p", {}, t(lang, "onb_contact_ro", { name: contact.name, channel: fieldText(lang, onFile, "channel") })),
        label(ctx, "p", "onb_contact_why", null, { class: "hint" }),
      ];
    }
    if (step === "money") {
      return [
        label(ctx, "h3", "onb_money_title"),
        el("p", {}, t(lang, "onb_money_ro", { amount: onFile.emergency_allowance, currency: onFile.currency })),
        label(ctx, "p", "onb_money_why", null, { class: "hint" }),
      ];
    }
    return [
      label(ctx, "h3", "onb_question_title"),
      el("p", {}, t(lang, "onb_question_ro", { question: t(lang, "sample_question") })),
      label(ctx, "p", "onb_question_why", null, { class: "hint" }),
      label(ctx, "p", "onb_rescue_note", null, { class: "hint" }),
    ];
  }

  function backButton(onBack) {
    return label(ctx, "button", "onb_back", null, { type: "button", class: "btn", id: "onb-back", onclick: onBack });
  }

  function stepPage() {
    const step = PLAN_STEPS[index];
    const next = label(ctx, "button", "onb_next", null, {
      type: "button",
      class: "btn btn-primary",
      id: "onb-next",
      onclick: () => {
        if (index < PLAN_STEPS.length - 1) index += 1;
        else page = "message";
        draw();
      },
    });
    const back =
      index > 0 || mode === "all"
        ? backButton(() => {
            if (index > 0) {
              index -= 1;
              draw();
            } else {
              page = "trip";
              draw();
            }
          })
        : null;
    return el(
      "div",
      { class: "onb" },
      label(ctx, "h2", "onb_plan_title"),
      label(ctx, "p", "onb_plan_intro", null, { class: "intro", id: "onb-plan-intro" }),
      label(ctx, "p", "onb_step_n", { n: index + 1, total: PLAN_STEPS.length }, { class: "hint" }),
      el("div", { class: `onb-step${READ_ONLY_STEPS.has(step) ? " onb-read-only" : ""}`, id: "onb-step", "data-step": step }, stepBody(step)),
      el("div", { class: "btn-row" }, back, next),
      skipRow(),
    );
  }

  // The end of the steps: one message with only what changed, for the student to read and send themselves.
  function messagePage() {
    const words = composeMessage(ctx.lang(), planChanges(onFile, draft), onFile);
    const finish = mode === "all" ? "chat" : "me";
    const back = backButton(() => {
      page = "step";
      index = PLAN_STEPS.length - 1;
      draw();
    });
    if (!words) {
      return el(
        "div",
        { class: "onb" },
        label(ctx, "h2", "onb_message_title"),
        label(ctx, "p", "onb_message_none", null, { id: "onb-message-none" }),
        el("div", { class: "btn-row" }, back, label(ctx, "button", "onb_done", null, { type: "button", class: "btn btn-primary", id: "onb-done", onclick: () => onFinish(finish) })),
      );
    }
    return el(
      "div",
      { class: "onb" },
      label(ctx, "h2", "onb_message_title"),
      label(ctx, "p", "onb_message_intro", null, { class: "intro" }),
      el("p", { class: "card onb-message", id: "onb-message" }, words),
      el(
        "div",
        { class: "btn-row" },
        back,
        label(ctx, "button", "onb_put_in_chat", null, { type: "button", class: "btn btn-primary", id: "onb-put-in-chat", onclick: () => onFinish("chat", words) }),
      ),
    );
  }

  // Country names, the values on file and the message are written in the chosen language, so a change redraws.
  return {
    start,
    relang: () => {
      if (page === "trip" || onFile) draw();
    },
  };
}
