// The ledger screen: GET /ledger/{user_id} and GET /ledger/{user_id}/verify, read together and shown together.
// Nothing here writes: both calls are reads (docs/api.md).
import { el, errorText, label } from "../dom.js";
import { entryLabel, verifyLines } from "../ledger-status.js";

const TONES = { ok: "card-ok", warn: "card-warn", danger: "card-danger", info: "" };

export function ledgerView(ctx, root) {
  const status = el("div", { class: "status-list", id: "ledger-status", "aria-live": "polite" });
  const count = el("p", { class: "hint", id: "ledger-count" });
  const list = el("ul", { class: "entries", id: "ledger-entries" });
  const error = el("p", { class: "error", id: "ledger-error", role: "alert" });
  const refresh = label(ctx, "button", "ledger_refresh", null, { type: "button", class: "btn", id: "ledger-refresh" });

  async function load() {
    refresh.disabled = true;
    error.replaceChildren();
    try {
      const [entries, verify] = await Promise.all([ctx.api.ledger(ctx.userId), ctx.api.verify(ctx.userId)]);
      draw(entries, verify);
    } catch (failure) {
      error.textContent = errorText(ctx, failure);
    } finally {
      refresh.disabled = false;
    }
  }

  function draw(entries, verify) {
    status.replaceChildren(
      ...verifyLines(verify).map((line) =>
        label(ctx, "p", line.key, line.values, { class: `card ${TONES[line.tone]}`, "data-part": line.part }),
      ),
    );
    count.replaceChildren(label(ctx, "span", "entries_count", { count: entries.length }));
    const broken = verify.first_broken_seq;
    const newestFirst = [...entries].reverse();
    list.replaceChildren(
      ...(newestFirst.length === 0
        ? [label(ctx, "li", "ledger_empty", null, { id: "ledger-empty" })]
        : newestFirst.map((entry) =>
            el(
              "li",
              { class: entry.seq === broken ? "broken" : null, "data-seq": entry.seq },
              el(
                "details",
                {},
                el(
                  "summary",
                  {},
                  el("strong", {}, `#${entry.seq}`),
                  el("span", {}, entryLabel(entry)),
                  entry.seq === broken ? label(ctx, "span", "entry_broken", null, { class: "badge" }) : null,
                  el("span", { class: "hint" }, entry.ts),
                ),
                el("pre", { class: "mono" }, JSON.stringify({ payload: entry.payload, prev_hash: entry.prev_hash, hash: entry.hash }, null, 2)),
              ),
            ),
          )),
    );
  }

  refresh.addEventListener("click", load);
  root.replaceChildren(
    el("div", { class: "btn-row" }, label(ctx, "h2", "ledger_title"), refresh),
    status,
    error,
    count,
    list,
  );
  return { shown: load };
}
