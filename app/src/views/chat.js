// The chat screen. The student's own words go in the message box and anything they pasted goes in the
// separate paste box. A paste or a drop into the message box is moved to the paste box, because text in
// `text` counts as the student's own instruction (docs/api.md, "Note to lane C").
import { el, errorText, label } from "../dom.js";
import { t } from "../i18n.js";
import { chatBody, confirmBody } from "../requests.js";
import { renderReply } from "./reply.js";
import { greeting } from "../tailoring.js";

// Source: docs/api.md, POST /chat: text is 1 to 4,000 characters and pasted_text 1 to 20,000.
const MAX_TEXT = 4000;
const MAX_PASTED = 20000;

export function chatView(ctx, root) {
  const thread = el("div", { class: "thread", id: "chat-thread", "aria-live": "polite" });
  const typed = el("textarea", { id: "chat-text", rows: 2, maxlength: MAX_TEXT, "data-i18n-placeholder": "message_placeholder" });
  typed.placeholder = t(ctx.lang(), "message_placeholder");
  const pasted = el("textarea", { id: "chat-paste", rows: 4, maxlength: MAX_PASTED });
  const pasteBox = el(
    "details",
    { class: "paste-box", id: "chat-paste-box" },
    label(ctx, "summary", "paste_label"),
    label(ctx, "p", "paste_help", null, { class: "hint" }),
    pasted,
  );
  const note = el("p", { class: "hint", id: "chat-note", "aria-live": "polite" });
  const error = el("p", { class: "error", id: "chat-error", role: "alert" });
  const send = label(ctx, "button", "send", null, { type: "submit", class: "btn btn-primary", id: "chat-send" });

  function moveToPasteBox(text) {
    if (!text) return;
    pasted.value = pasted.value ? `${pasted.value}\n${text}` : text;
    pasteBox.open = true;
    note.replaceChildren(label(ctx, "span", "paste_moved"));
  }
  typed.addEventListener("paste", (event) => {
    event.preventDefault();
    moveToPasteBox(event.clipboardData?.getData("text/plain") ?? "");
  });
  typed.addEventListener("drop", (event) => {
    event.preventDefault();
    moveToPasteBox(event.dataTransfer?.getData("text/plain") ?? "");
  });

  async function submit(event) {
    event.preventDefault();
    error.replaceChildren();
    const body = chatBody(ctx.userId, typed.value, pasted.value, ctx.lang());
    if (body === null) {
      error.replaceChildren(label(ctx, "span", "text_required"));
      typed.focus();
      return;
    }
    send.disabled = true;
    try {
      const reply = await ctx.api.chat(body);
      thread.append(yourMessage(ctx, body), lifelineMessage(ctx, reply));
      typed.value = "";
      pasted.value = "";
      pasteBox.open = false;
      note.replaceChildren();
      thread.lastElementChild.scrollIntoView({ block: "start", behavior: "smooth" });
    } catch (failure) {
      // Nothing was done, so the draft stays for another try.
      error.textContent = errorText(ctx, failure);
    } finally {
      send.disabled = false;
    }
  }

  // Lets the Guide put an example's words in the message box. They are the app's own words, so they go in
  // the typed box, and the paste box is left as it is.
  ctx.fillMessage = (words) => {
    typed.value = words;
    typed.focus();
  };

  // Lets the confirmation card (step 3) add Lifeline's answer to /confirm into the same thread.
  ctx.addToThread = (node) => {
    thread.append(node);
    node.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  // The greeting names the place of study from the onboarding, and is plain without a trip.
  const hello = el("p", { class: "chat-greeting", id: "chat-greeting" });
  ctx.refreshGreeting = () => {
    hello.textContent = greeting(ctx.profile.trip, ctx.lang());
  };
  ctx.refreshGreeting();

  root.replaceChildren(
    hello,
    label(ctx, "p", "chat_intro", null, { class: "intro" }),
    thread,
    el(
      "form",
      { class: "composer", onsubmit: submit },
      el("label", { class: "field" }, label(ctx, "span", "message_label"), typed),
      pasteBox,
      note,
      error,
      send,
    ),
  );
}

function yourMessage(ctx, body) {
  return el(
    "div",
    { class: "msg msg-you" },
    label(ctx, "span", "you", null, { class: "msg-who" }),
    el("div", { class: "bubble" }, body.text),
    body.pasted_text ? el("div", { class: "pasted" }, label(ctx, "span", "pasted_badge", null, { class: "badge" }), " ", body.pasted_text) : null,
  );
}

export function lifelineMessage(ctx, reply) {
  // A yes goes to POST /confirm; its answer, which may offer the next route under the same token, joins the thread.
  const onConfirm = async (token) => {
    const answer = await ctx.api.confirm(confirmBody(ctx.userId, token, ctx.lang()));
    ctx.addToThread(lifelineMessage(ctx, answer));
  };
  return el(
    "div",
    { class: "msg msg-lifeline" },
    label(ctx, "span", "lifeline", null, { class: "msg-who" }),
    renderReply(ctx, reply, { onConfirm }),
  );
}
