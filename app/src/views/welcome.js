// The welcome screen, shown on opening before the tabs: the logo, one sentence on what Lifeline is for, three
// short cards to swipe or tap through, and one way in, as the demo student. There is no sign in, so there is no
// password field and no account; nothing here is stored, so the welcome shows again on every visit.
import { el, label } from "../dom.js";
import { WELCOME_CARDS } from "../guide-content.js";
import { logo } from "../logo.js";

export function welcomeView(ctx, root, onContinue) {
  const track = el(
    "div",
    { class: "welcome-cards", id: "welcome-cards" },
    WELCOME_CARDS.map((card, index) =>
      el(
        "article",
        { class: "card welcome-card", id: `welcome-card-${card.id}`, "data-index": index },
        label(ctx, "h2", card.title),
        el("ul", {}, card.lines.map((key) => label(ctx, "li", key))),
      ),
    ),
  );
  const cards = () => [...track.querySelectorAll(".welcome-card")];
  const dots = WELCOME_CARDS.map((card, index) =>
    el(
      "button",
      { type: "button", class: "welcome-dot", "data-index": index, onclick: () => go(index) },
      label(ctx, "span", "welcome_card_n", { n: index + 1 }, { class: "sr-only" }),
    ),
  );
  const next = label(ctx, "button", "welcome_next", null, { type: "button", class: "btn", id: "welcome-next", onclick: () => go(current() + 1) });

  function current() {
    const width = track.clientWidth || 1;
    return Math.min(WELCOME_CARDS.length - 1, Math.max(0, Math.round(track.scrollLeft / width)));
  }
  function go(index) {
    const target = cards()[Math.min(index, WELCOME_CARDS.length - 1)];
    target.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
    mark(Number(target.dataset.index));
  }
  function mark(index) {
    dots.forEach((dot, at) => dot.setAttribute("aria-current", at === index ? "true" : "false"));
    next.disabled = index === WELCOME_CARDS.length - 1;
  }
  track.addEventListener("scroll", () => mark(current()), { passive: true });

  root.replaceChildren(
    el("div", { class: "welcome-logo" }, logo(60)),
    label(ctx, "p", "welcome_tagline", null, { class: "welcome-tagline", id: "welcome-tagline" }),
    track,
    el("div", { class: "welcome-nav" }, el("div", { class: "welcome-dots" }, dots), next),
    label(ctx, "button", "welcome_continue", null, { type: "button", class: "btn btn-primary", id: "welcome-continue", onclick: onContinue }),
    label(ctx, "p", "welcome_demo_note", null, { class: "hint", id: "welcome-demo-note" }),
  );
  mark(0);
  return { shown: () => go(0) };
}
