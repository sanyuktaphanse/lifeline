// The welcome screen, shown on opening before the tabs: the logo, one sentence on what Lifeline is for, three
// short cards to swipe or tap through, and one way in, as the demo student. There is no sign in, so there is no
// password field and no account; nothing here is stored, so the welcome shows again on every visit.
import { el, label } from "../dom.js";
import { WELCOME_CARDS } from "../guide-content.js";
import { logo, orb } from "../logo.js";
import { t } from "../i18n.js";
import { slideDone } from "../slider.js";

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
  const next = label(ctx, "button", "welcome_next", null, { type: "button", class: "btn", id: "welcome-next", onclick: () => go((heading ?? current()) + 1) });

  function current() {
    const width = track.clientWidth || 1;
    return Math.min(WELCOME_CARDS.length - 1, Math.max(0, Math.round(track.scrollLeft / width)));
  }
  // The card a tap is scrolling to. A second Next during the smooth scroll counts from it, not from where the
  // scroll happens to be, so it never lands on the same card twice.
  let heading = null;
  function go(index) {
    const target = cards()[Math.min(index, WELCOME_CARDS.length - 1)];
    heading = Number(target.dataset.index);
    target.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
    mark(Number(target.dataset.index));
  }
  function mark(index) {
    dots.forEach((dot, at) => dot.setAttribute("aria-current", at === index ? "true" : "false"));
    next.disabled = index === WELCOME_CARDS.length - 1;
  }
  track.addEventListener(
    "scroll",
    () => {
      if (heading !== null && current() !== heading) return;
      heading = null;
      mark(current());
    },
    { passive: true },
  );
  // If a swipe interrupts the scroll, the card it stops on wins.
  track.addEventListener("scrollend", () => {
    heading = null;
    mark(current());
  });

  // Slide to start. The knob is a button: Enter or Space starts at once. A tap that does not slide nudges the
  // knob to show it moves. The plain Continue button below stays as the fallback.
  const fill = el("span", { class: "slider-fill", "aria-hidden": "true" });
  const knob = el("button", { type: "button", class: "slider-knob", id: "welcome-slide-knob", "data-i18n-label": "welcome_slide_knob", "aria-label": t(ctx.lang(), "welcome_slide_knob") }, "›");
  const slider = el("div", { class: "slider", id: "welcome-slider" }, fill, label(ctx, "span", "welcome_slide", null, { class: "slider-label", "aria-hidden": "true" }), knob);
  let startX = null;
  let x = 0;
  const max = () => slider.clientWidth - knob.offsetWidth - 12;
  const paint = () => {
    knob.style.transform = `translateX(${x}px)`;
    fill.style.width = `${x + knob.offsetWidth + 6}px`;
  };
  knob.addEventListener("pointerdown", (event) => {
    startX = event.clientX - x;
    knob.setPointerCapture(event.pointerId);
    slider.classList.add("dragging");
  });
  knob.addEventListener("pointermove", (event) => {
    if (startX === null) return;
    x = Math.max(0, Math.min(max(), event.clientX - startX));
    paint();
  });
  const release = () => {
    if (startX === null) return;
    startX = null;
    slider.classList.remove("dragging");
    const done = slideDone(x, max());
    x = done ? max() : 0;
    paint();
    if (done) {
      onContinue();
      x = 0;
      paint();
    }
  };
  knob.addEventListener("pointerup", release);
  knob.addEventListener("pointercancel", release);
  // A click with no pointer travel is a keyboard press (detail 0): it starts at once.
  knob.addEventListener("click", (event) => {
    if (event.detail === 0) onContinue();
  });

  root.replaceChildren(
    el("div", { class: "welcome-logo" }, logo(36)),
    orb("large"),
    label(ctx, "p", "welcome_tagline", null, { class: "welcome-tagline", id: "welcome-tagline" }),
    track,
    el("div", { class: "welcome-nav" }, el("div", { class: "welcome-dots" }, dots), next),
    slider,
    label(ctx, "button", "welcome_continue", null, { type: "button", class: "btn", id: "welcome-continue", onclick: onContinue }),
    label(ctx, "p", "welcome_demo_note", null, { class: "hint", id: "welcome-demo-note" }),
  );
  mark(0);
  return { shown: () => go(0) };
}
