// The onboarding after the welcome: three questions about the trip, then the five steps of a safety net, then a
// summary. Everything stays in page memory, in ctx.profile, and nothing is sent to the server: the API has no
// endpoint for a plan, and the live rescue reads the demo student's plan in fixtures/demo_user.yaml.
// The safety answer is read only to know that one was typed, then cleared, so it is never kept, even in memory.
// Skip keeps the sample plan. Me opens the same screens again with "trip" or "plan" to change one part.
import { el, label } from "../dom.js";
import { t } from "../i18n.js";
import { countryGroups, countryName, hasRules } from "../countries.js";
import { planFacts } from "./me.js";
import {
  CHANNELS, EMERGENCY_CHOICES, PLAN_STEPS, PURPOSES, RELATIONSHIPS, SAFETY_QUESTIONS, SAMPLE_PLAN,
  cardChoices, setAnswer, stepReady, tripReady,
} from "../onboarding.js";

export function onboardingView(ctx, root, onFinish) {
  let mode = "all";
  let page = "trip";
  let index = 0;
  let trip = {};
  let draft = {};

  function start(nextMode) {
    mode = nextMode;
    trip = { ...(ctx.profile.trip ?? {}) };
    draft = ctx.profile.plan ? { ...ctx.profile.plan, contact: { ...ctx.profile.plan.contact } } : {};
    page = mode === "plan" ? "step" : "trip";
    index = 0;
    draw();
  }

  // Skip leaves the plan as it was: the sample plan, unless one was set before. From Me it changes nothing.
  function skip() {
    onFinish(mode === "all" ? "chat" : "me");
  }

  function draw() {
    root.replaceChildren(page === "trip" ? tripPage() : page === "step" ? stepPage() : summaryPage());
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
      page = "step";
      index = 0;
      draw();
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

  function select(id, keys, current, onPick, keyOf = (value) => value) {
    const node = el(
      "select",
      { id },
      el("option", { value: "" }, "…"),
      keys.map((value) => label(ctx, "option", keyOf(value), null, { value })),
    );
    node.value = current ?? "";
    node.addEventListener("change", () => onPick(node.value || null));
    return node;
  }

  function field(key, id, control) {
    return el("div", { class: "field" }, label(ctx, "label", key, null, { for: id }), control);
  }

  function stepPage() {
    const step = PLAN_STEPS[index];
    const next = label(ctx, "button", "onb_next", null, { type: "button", class: "btn btn-primary", id: "onb-next" });
    let answer = null;
    const ready = () => {
      const probe = step === "question" && answer?.value.trim() ? setAnswer(draft, answer.value) : draft;
      next.disabled = !stepReady(step, probe);
    };
    let body;
    if (step === "card") {
      const choices = cardChoices(ctx.profile.trip);
      body = [
        label(ctx, "h3", "onb_card_q"),
        label(ctx, "p", "onb_card_common", null, { class: "hint" }),
        radios("onb-card", choices.map((card) => ({ value: card.id, key: card.key, text: card.name })), draft.card, (value) => {
          draft.card = value;
          ready();
        }),
        label(ctx, "p", "onb_card_note", null, { class: "hint" }),
        el("ul", { class: "hint" }, label(ctx, "li", "onb_unsure_1"), label(ctx, "li", "onb_unsure_2")),
      ];
    } else if (step === "backup") {
      body = [
        label(ctx, "h3", "onb_backup_q"),
        label(ctx, "p", "onb_backup_hint", null, { class: "hint" }),
        radios("onb-backup", [{ value: "yes", key: "onb_yes" }, { value: "no", key: "onb_no" }], draft.backup === undefined ? null : draft.backup ? "yes" : "no", (value) => {
          draft.backup = value === "yes";
          ready();
        }),
      ];
    } else if (step === "question") {
      answer = el("input", { id: "onb-answer", type: "text", autocomplete: "off", spellcheck: "false", maxlength: 200 });
      answer.addEventListener("input", ready);
      answer.addEventListener("paste", (event) => event.preventDefault());
      body = [
        field("onb_question_q", "onb-question", select("onb-question", SAFETY_QUESTIONS, draft.question, (value) => {
          draft.question = value;
          ready();
        })),
        field("onb_answer", "onb-answer", answer),
        label(ctx, "p", "onb_answer_note", null, { class: "hint" }),
        label(ctx, "p", "onb_rescue_note", null, { class: "card card-warn onb-rescue-note" }),
      ];
    } else if (step === "contact") {
      const contact = (draft.contact ??= {});
      const text = (id, key, part, type) => {
        const input = el("input", { id, type, autocomplete: "off", maxlength: 120 });
        input.value = contact[part] ?? "";
        input.addEventListener("input", () => {
          contact[part] = input.value;
          ready();
        });
        return field(key, id, input);
      };
      body = [
        label(ctx, "h3", "onb_contact_q"),
        text("onb-contact-name", "onb_contact_name", "name", "text"),
        field("onb_contact_rel", "onb-contact-rel", select("onb-contact-rel", RELATIONSHIPS, contact.relationship, (value) => {
          contact.relationship = value;
          ready();
        }, (value) => `rel_${value}`)),
        text("onb-contact-phone", "onb_contact_phone", "phone", "tel"),
        text("onb-contact-email", "onb_contact_email", "email", "email"),
        field("onb_contact_channel", "onb-contact-channel", select("onb-contact-channel", CHANNELS, contact.channel, (value) => {
          contact.channel = value;
          ready();
        }, (value) => `channel_${value}`)),
        label(ctx, "p", "onb_on_device", null, { class: "hint" }),
      ];
    } else {
      body = [
        label(ctx, "h3", "onb_money_q"),
        label(ctx, "p", "onb_money_hint", null, { class: "hint" }),
        radios(
          "onb-money",
          EMERGENCY_CHOICES.map((value) =>
            value === "none" ? { value, key: "onb_money_none" } : { value, key: "onb_money_amount", values: { amount: value, currency: SAMPLE_PLAN.currency } },
          ),
          draft.money,
          (value) => {
            draft.money = value;
            ready();
          },
        ),
      ];
    }

    next.addEventListener("click", () => {
      if (answer) {
        if (answer.value.trim()) draft = setAnswer(draft, answer.value);
        answer.value = "";
      }
      if (!stepReady(step, draft)) return;
      if (index < PLAN_STEPS.length - 1) index += 1;
      else page = "summary";
      draw();
    });
    const canGoBack = index > 0 || mode === "all";
    const back = canGoBack
      ? label(ctx, "button", "onb_back", null, {
          type: "button",
          class: "btn",
          id: "onb-back",
          onclick: () => {
            if (answer) answer.value = "";
            if (index > 0) index -= 1;
            else page = "trip";
            draw();
          },
        })
      : null;
    ready();
    return el(
      "div",
      { class: "onb" },
      label(ctx, "h2", "onb_plan_title"),
      label(ctx, "p", "onb_step_n", { n: index + 1 }, { class: "hint" }),
      el("div", { class: "onb-step", id: "onb-step", "data-step": step }, body),
      el("div", { class: "btn-row" }, back, next),
      skipRow(),
    );
  }

  function summaryPage() {
    const done = label(ctx, "button", "onb_done", null, {
      type: "button",
      class: "btn btn-primary",
      id: "onb-done",
      onclick: () => {
        ctx.profile.plan = { ...draft, contact: { ...draft.contact } };
        onFinish(mode === "all" ? "chat" : "me");
      },
    });
    return el(
      "div",
      { class: "onb" },
      label(ctx, "h2", "onb_done_title"),
      el("div", { class: "card", id: "onb-summary" }, planFacts(ctx, draft), label(ctx, "p", "onb_nothing_sent", null, { class: "hint" })),
      done,
    );
  }

  // Country names and group headings come from Intl, not from data-i18n labels, so a language change redraws.
  // Only the trip page shows them; a step page keeps what was typed, and relabel() changes its labels.
  return {
    start,
    relang: () => {
      if (page === "trip" || page === "summary") draw();
    },
  };
}
