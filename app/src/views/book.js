// The Book and pay safely page, opened from Home. Everything on it is the app's own words; nothing is sent or stored.
// The deposit ticks live in the checkboxes only, so closing the page clears them. "Check a message" opens Chat with
// the question typed and the paste box open, so the message the student pastes goes in pasted_text, and nothing is
// sent until they tap Send.
import { el, label } from "../dom.js";
import { APP_GROUPS, CHECKS, DEPOSIT } from "../book.js";

export function bookView(ctx, root, { onCheck, onClose }) {
  root.replaceChildren(
    label(ctx, "h2", "book_title"),
    label(ctx, "p", "book_intro", null, { class: "intro" }),
    el(
      "section",
      { class: "card", id: "book-checks" },
      label(ctx, "h3", "book_checks_title"),
      el("ul", { class: "book-list" }, CHECKS.map((key) => label(ctx, "li", key))),
      label(ctx, "button", "book_check_button", null, { type: "button", class: "btn", id: "book-check", onclick: onCheck }),
    ),
    el(
      "section",
      { class: "card", id: "book-deposit" },
      label(ctx, "h3", "book_deposit_title"),
      label(ctx, "p", "book_deposit_intro", null, { class: "hint" }),
      DEPOSIT.map((key) =>
        el("label", { class: "onb-option book-tick" }, el("input", { type: "checkbox", id: `book-${key}` }), label(ctx, "span", key)),
      ),
    ),
    el(
      "section",
      { class: "card", id: "book-apps" },
      label(ctx, "h3", "book_apps_title"),
      label(ctx, "p", "book_apps_order", null, { class: "hint" }),
      APP_GROUPS.map((group) =>
        el(
          "div",
          { class: "book-group" },
          label(ctx, "h4", group.key),
          el("ul", {}, group.apps.map((name) => el("li", {}, name))),
          group.key === "book_group_flights" ? label(ctx, "p", "book_flights_hint", null, { class: "hint" }) : null,
        ),
      ),
      label(ctx, "p", "book_apps_note", null, { class: "card card-warn book-note", id: "book-apps-note" }),
    ),
    label(ctx, "button", "book_close", null, { type: "button", class: "btn", id: "book-close", onclick: onClose }),
  );
  return {};
}
