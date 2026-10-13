// Draws one AgentReply, reading its fields in the order docs/api.md, "Reading an AgentReply", gives.
// All server text is set as text, never as HTML.
import { el, label } from "../dom.js";
import { confirmationCard } from "./confirmation.js";
import { partsOf } from "../reply-text.js";
import { renderMarkdown } from "../markdown.js";

// The blocked request sentences go first and the "This turn:" sentence last, each on its own line, because
// code wrote them from the ledger and the app can rely on them even when the model's words are wrong.
export function renderReply(ctx, reply, { onConfirm } = {}) {
  const { blocked, body, turn } = partsOf(reply);
  const parts = blocked.map((sentence) =>
    el("div", { class: "reply-blocked" }, label(ctx, "span", "blocked_label", null, { class: "blocked-label" }), el("span", { class: "blocked-text" }, sentence)),
  );
  // Only the model's words are read as markdown; the two sentences code writes stay plain text.
  if (body) parts.push(el("div", { class: "bubble reply-body" }, renderMarkdown(body)));
  if (reply.receipt) parts.push(receiptCard(ctx, reply.receipt));
  if (reply.freeze) parts.push(resultCard(ctx, "freeze_title", reply.freeze, "freeze"));
  if (reply.cancel) parts.push(resultCard(ctx, "cancel_title", reply.cancel, "cancel"));
  if (reply.confirmation && onConfirm) parts.push(confirmationCard(ctx, reply.confirmation, onConfirm));
  if (reply.decision && reply.decision.allowed === false) parts.push(refusalCard(ctx, reply.decision));
  if (turn) {
    parts.push(el("div", { class: "reply-turn" }, label(ctx, "span", "turn_label", null, { class: "turn-label" }), el("span", { class: "turn-text" }, turn)));
  }
  return el("div", { class: "reply" }, parts);
}

function receiptCard(ctx, receipt) {
  const bad = receipt.status === "failed" || receipt.status === "returned";
  return el(
    "div",
    { class: `card receipt ${bad ? "card-danger" : "card-ok"}` },
    label(ctx, "h3", "receipt_title"),
    el(
      "dl",
      { class: "facts" },
      label(ctx, "dt", "field_receipt"),
      el("dd", { class: "mono" }, receipt.receipt_id),
      label(ctx, "dt", "field_amount"),
      el("dd", {}, `${receipt.amount} ${receipt.currency}`),
    ),
    label(ctx, "p", "status_label", { status: receipt.status }),
    receipt.simulated ? label(ctx, "p", "receipt_simulated", null, { class: "hint" }) : null,
  );
}

function resultCard(ctx, titleKey, result, kind) {
  const done = result.status === "done";
  return el(
    "div",
    { class: `card ${kind} ${done ? "card-ok" : "card-warn"}` },
    label(ctx, "h3", titleKey),
    label(ctx, "p", "status_label", { status: result.status }),
    result.reason ? el("p", {}, result.reason) : null,
    result.deep_link ? issuerLink(ctx, result.deep_link, "open_issuer_app") : null,
  );
}

function refusalCard(ctx, decision) {
  return el(
    "div",
    { class: "card card-danger refusal" },
    label(ctx, "h3", "refused_title"),
    label(ctx, "p", "rules", { ids: decision.rule_ids.join(", ") }),
    el("ul", {}, decision.reasons.map((reason) => el("li", {}, reason))),
  );
}

// Only web links are opened, so a link from a rail can never run script in the app.
export function issuerLink(ctx, href, key) {
  let url;
  try {
    url = new URL(href);
  } catch {
    return el("p", { class: "mono" }, href);
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return el("p", { class: "mono" }, href);
  return el("a", { class: "btn", href: url.href, target: "_blank", rel: "noopener noreferrer" }, label(ctx, "span", key));
}
