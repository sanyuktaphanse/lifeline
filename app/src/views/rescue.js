// The lost or stolen card rescue (docs/api.md, "Rescue"). What the screen offers comes only from the latest
// reply's rescue.do_now. Every field takes typed words only: pasting and dropping are refused, because a pasted
// message sent as text would count as the student's own (rule 1 of "Rules the app must keep"). The identity
// answer is cleared from its box as soon as it is sent and is never kept anywhere.
import { el, errorText, label } from "../dom.js";
import { rescueStartBody, rescueStepBody } from "../requests.js";
import { stepFor } from "../rescue-steps.js";
import { issuerLink, renderReply } from "./reply.js";

// Source: docs/api.md, POST /rescue/start: text is 1 to 4,000 characters.
const MAX_TEXT = 4000;
const TRIGGERS = [
  ["lost", "card_lost", "rescue_lost"],
  ["stolen", "card_stolen", "rescue_stolen"],
];

export function rescueView(ctx, root) {
  const thread = el("div", { class: "thread", id: "rescue-thread", "aria-live": "polite" });
  const status = el("div", { class: "status-list", id: "rescue-status" });
  const controls = el("div", { id: "rescue-controls" });
  const note = el("p", { class: "hint", id: "rescue-note", "aria-live": "polite" });
  const error = el("p", { class: "error", id: "rescue-error", role: "alert" });
  const replies = [];

  function typedOnly(field) {
    const refuse = (event) => {
      event.preventDefault();
      note.replaceChildren(label(ctx, "span", "rescue_no_paste"));
    };
    field.addEventListener("paste", refuse);
    field.addEventListener("drop", refuse);
    return field;
  }

  async function send(call) {
    error.replaceChildren();
    for (const button of controls.querySelectorAll("button")) button.disabled = true;
    try {
      show(await call());
    } catch (failure) {
      error.textContent = errorText(ctx, failure);
      for (const button of controls.querySelectorAll("button")) button.disabled = false;
      throw failure;
    }
  }
  const step = (parts) => send(() => ctx.api.rescueStep(rescueStepBody(ctx.userId, parts, ctx.lang())));
  // The confirmation card calls this with the token; a failure is rethrown so the card lets the student retry.
  const confirmStep = (token) => step({ token });

  // Older replies are kept as a record without their confirmation cards; only the latest can be confirmed.
  function show(reply) {
    replies.push(reply);
    thread.replaceChildren(
      ...replies.map((item, index) =>
        el(
          "div",
          { class: "msg msg-lifeline" },
          label(ctx, "span", "lifeline", null, { class: "msg-who" }),
          renderReply(ctx, item, index === replies.length - 1 ? { onConfirm: confirmStep } : {}),
        ),
      ),
    );
    drawStatus(reply.rescue ?? {});
    drawControls(stepFor(reply.rescue, Boolean(reply.confirmation)));
    thread.lastElementChild.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  function drawStatus(rescue) {
    status.replaceChildren(
      rescue.state_after ? label(ctx, "p", "rescue_step", { state: rescue.state_after }, { id: "rescue-step", class: "hint" }) : null,
      rescue.live_instrument ? label(ctx, "p", "rescue_backup", { card: rescue.live_instrument }, { id: "rescue-backup" }) : null,
      rescue.issuer_link ? issuerLink(ctx, rescue.issuer_link, "rescue_issuer") : null,
    );
  }

  function drawControls(next) {
    note.replaceChildren();
    switch (next.kind) {
      case "start":
        controls.replaceChildren(startForm());
        break;
      case "answer":
        controls.replaceChildren(answerForm());
        break;
      case "locked":
        controls.replaceChildren(label(ctx, "p", "rescue_locked", null, { id: "rescue-locked", class: "card card-danger" }));
        break;
      case "choose":
        controls.replaceChildren(
          el(
            "div",
            { class: "card", id: "rescue-cards" },
            label(ctx, "h3", "rescue_choose_card"),
            el(
              "div",
              { class: "btn-row" },
              next.cards.map((name) => el("button", { type: "button", class: "btn", onclick: () => step({ text: name }).catch(() => {}) }, name)),
            ),
          ),
        );
        break;
      case "confirm":
        // The confirm button is on the card in the reply above; skipping is its own button here.
        controls.replaceChildren(
          next.skip
            ? label(ctx, "button", "rescue_skip", null, { type: "button", class: "btn", id: "rescue-skip", onclick: () => step({}).catch(() => {}) })
            : "",
        );
        break;
      case "reoffer":
        controls.replaceChildren(
          label(ctx, "button", "rescue_reoffer", null, { type: "button", class: "btn btn-primary", id: "rescue-reoffer", onclick: () => step({}).catch(() => {}) }),
        );
        break;
      case "done":
        controls.replaceChildren(label(ctx, "p", "rescue_done", null, { id: "rescue-done", class: "card card-ok" }));
        break;
      default:
        controls.replaceChildren();
    }
  }

  function startForm() {
    const words = typedOnly(el("textarea", { id: "rescue-words", rows: 2, maxlength: MAX_TEXT, autocomplete: "off" }));
    const local = el("p", { class: "error" });
    const choices = TRIGGERS.map(([id, value, key], index) =>
      el(
        "label",
        { class: "choice" },
        el("input", { type: "radio", name: "rescue-trigger", id: `rescue-trigger-${id}`, value, checked: index === 0 }),
        " ",
        label(ctx, "span", key),
      ),
    );
    const start = label(ctx, "button", "rescue_start", null, { type: "submit", class: "btn btn-primary", id: "rescue-start" });
    return el(
      "form",
      {
        class: "card",
        onsubmit: (event) => {
          event.preventDefault();
          const trigger = controls.querySelector('input[name="rescue-trigger"]:checked')?.value ?? "card_lost";
          const body = rescueStartBody(ctx.userId, trigger, words.value, ctx.lang());
          if (body === null) {
            local.replaceChildren(label(ctx, "span", "rescue_words_required"));
            return;
          }
          send(() => ctx.api.rescueStart(body)).catch(() => {});
        },
      },
      label(ctx, "p", "rescue_intro", null, { class: "intro" }),
      el("fieldset", { class: "choices" }, label(ctx, "legend", "rescue_trigger_label"), choices),
      el("label", { class: "field" }, label(ctx, "span", "rescue_words_label"), words),
      label(ctx, "p", "rescue_no_paste", null, { class: "hint" }),
      local,
      start,
    );
  }

  function answerForm() {
    const answer = typedOnly(
      el("input", { type: "text", id: "rescue-answer", maxlength: MAX_TEXT, autocomplete: "off", autocapitalize: "off", spellcheck: "false" }),
    );
    const local = el("p", { class: "error" });
    return el(
      "form",
      {
        class: "card",
        onsubmit: (event) => {
          event.preventDefault();
          // An empty answer would be compared and count as a wrong one, so it is never sent.
          if (answer.value.trim() === "") {
            local.replaceChildren(label(ctx, "span", "rescue_answer_required"));
            return;
          }
          const text = answer.value;
          answer.value = "";
          step({ text }).catch(() => {});
        },
      },
      el("label", { class: "field" }, label(ctx, "span", "rescue_answer_label"), answer),
      local,
      label(ctx, "button", "rescue_answer_send", null, { type: "submit", class: "btn btn-primary", id: "rescue-answer-send" }),
    );
  }

  root.replaceChildren(thread, status, controls, note, error);
  drawControls({ kind: "start" });
}
