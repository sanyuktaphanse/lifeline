// Draws one AgentReply. All server text is set as text, never as HTML.
import { el } from "../dom.js";

export function renderReply(ctx, reply) {
  return el("div", { class: "reply" }, el("div", { class: "bubble reply-body" }, reply.text));
}
