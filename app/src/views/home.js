// Home: the greeting, the reminders under the bell, and four cards. Three cards send their words to the chat at
// once, in text, as the student's own request, and each shows the words it sends. The Lost card opens the
// rescue, which needs the student's own account of what happened. There is no balance: the API has no endpoint
// for one. Reminders come from GET /reminders/{user_id}, a read that writes nothing to the ledger.
import { el, errorText, label } from "../dom.js";
import { t } from "../i18n.js";
import { fromHome, greeting, homeStarter } from "../tailoring.js";
import { reminderItems } from "../reminders.js";

const LOCALES = { en: "en-GB", pt: "pt-BR", zh: "zh-CN" };

export function homeView(ctx, root, { send, openTab, openBook }) {
  let reminders = null;
  let failure = null;
  let open = false;

  function cards() {
    const lang = ctx.lang();
    const trip = ctx.profile.trip;
    const sending = (id, title, words) =>
      el(
        "button",
        { type: "button", class: "card home-card", "data-card": id, onclick: () => send(words) },
        el("strong", {}, title),
        el("span", { class: "hint home-card-sends" }, t(lang, "home_sends", { words })),
      );
    return el(
      "div",
      { class: "home-cards" },
      sending("rent", t(lang, "home_card_rent"), t(lang, "guide_ex_rent")),
      sending("home", fromHome(trip, lang), homeStarter(trip, lang) ?? t(lang, "starter_home_plain")),
      sending("scam", t(lang, "home_card_scam"), t(lang, "starter_scam")),
      el(
        "button",
        { type: "button", class: "card home-card", "data-card": "lost", onclick: () => openTab("rescue") },
        el("strong", {}, t(lang, "home_card_lost")),
        el("span", { class: "hint" }, t(lang, "home_card_lost_sub")),
      ),
    );
  }

  function reminderList() {
    const lang = ctx.lang();
    if (failure) return el("p", { class: "error", role: "alert" }, errorText(ctx, failure));
    if (!reminders) return null;
    const { items } = reminderItems(reminders);
    if (!items.length) return el("p", { class: "hint" }, t(lang, "home_reminders_none"));
    return el(
      "ul",
      {},
      items.map((item) =>
        el(
          "li",
          { "data-seq": item.seq },
          el("span", {}, item.text),
          " ",
          item.isDue ? el("span", { class: "badge" }, t(lang, "home_due")) : null,
          el("div", { class: "hint" }, item.due ? new Date(item.due).toLocaleDateString(LOCALES[lang] ?? lang, { day: "numeric", month: "long", year: "numeric" }) : t(lang, "home_no_date")),
        ),
      ),
    );
  }

  function draw() {
    const lang = ctx.lang();
    const dueCount = reminders ? reminderItems(reminders).dueCount : 0;
    const bell = el(
      "button",
      { type: "button", class: "btn bell", id: "home-bell", "aria-expanded": String(open), "aria-controls": "home-reminders" },
      el("span", {}, t(lang, "home_bell")),
      dueCount ? el("span", { class: "count", "aria-label": t(lang, "home_bell_due", { count: dueCount }) }, String(dueCount)) : null,
    );
    bell.addEventListener("click", () => {
      open = !open;
      draw();
    });
    root.replaceChildren(
      el("div", { class: "home-head" }, el("p", { class: "home-greeting", id: "home-greeting" }, greeting(ctx.profile.trip, lang)), bell),
      el("section", { class: "card", id: "home-reminders", hidden: !open }, el("h3", {}, t(lang, "home_reminders_title")), reminderList()),
      el("h2", {}, t(lang, "home_cards_title")),
      cards(),
      el(
        "button",
        { type: "button", class: "card home-card home-book", id: "open-book", onclick: openBook },
        el("span", { class: "hint" }, t(lang, "home_book")),
        el("strong", {}, t(lang, "home_book_open")),
      ),
    );
  }

  async function load() {
    draw();
    try {
      reminders = await ctx.api.reminders(ctx.userId);
      failure = null;
    } catch (error) {
      failure = error;
    }
    draw();
  }

  return { shown: load, relang: draw };
}
