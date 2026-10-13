// The Guide tab: what to do in each moment a student abroad meets, then how Lifeline protects her. Every
// sentence is a label in src/i18n.js, listed in src/guide-content.js. An example is the app's own words: tapping
// it puts them in the message box through onExample, never in the paste box. When the tab is shown it reads
// GET /ledger/{user_id}/verify once, a read that changes nothing, and shows what it says.
import { el, errorText, label } from "../dom.js";
import { GUIDE_SECTIONS, PROTECT_SECTIONS } from "../guide-content.js";
import { verifyLines } from "../ledger-status.js";

const TONES = { ok: "card-ok", warn: "card-warn", danger: "card-danger", info: "" };

export function guideView(ctx, root, onExample) {
  const status = el("div", { class: "status-list", id: "guide-verify", "aria-live": "polite" });
  const error = el("p", { class: "error", id: "guide-error", role: "alert" });

  function section(item, headingTag) {
    return el(
      "section",
      { class: "guide-section", id: `guide-${item.id}` },
      label(ctx, headingTag, item.title),
      item.lines.map((key) => label(ctx, "p", key)),
      item.examples?.length
        ? el(
            "div",
            { class: "examples" },
            label(ctx, "p", "guide_try", null, { class: "hint" }),
            item.examples.map((key) =>
              label(ctx, "button", key, null, {
                type: "button",
                class: "example",
                // The words as the button shows them now, in the language picked.
                onclick: (event) => onExample(event.currentTarget.textContent),
              }),
            ),
          )
        : null,
    );
  }

  async function shown() {
    error.replaceChildren();
    try {
      const verify = await ctx.api.verify(ctx.userId);
      status.replaceChildren(
        ...verifyLines(verify).map((line) =>
          label(ctx, "p", line.key, line.values, { class: `card ${TONES[line.tone]}`, "data-part": line.part }),
        ),
      );
    } catch (failure) {
      status.replaceChildren();
      error.textContent = errorText(ctx, failure);
    }
  }

  root.replaceChildren(
    label(ctx, "p", "guide_intro", null, { class: "intro" }),
    ...GUIDE_SECTIONS.map((item) => section(item, "h3")),
    el(
      "div",
      { class: "guide-protect", id: "guide-protect" },
      label(ctx, "h2", "guide_protect_title"),
      PROTECT_SECTIONS.map((item) => section(item, "h3")),
      el("div", { class: "guide-verify" }, label(ctx, "p", "guide_verify_title", null, { class: "hint" }), status, error),
    ),
  );
  return { shown };
}
