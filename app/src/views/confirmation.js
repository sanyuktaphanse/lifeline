// The confirmation card, drawn from an AgentReply's `confirmation` field. Used by the chat and by the rescue.
//
// The token lives only in this function's closure: it is never written to the page, to browser storage or
// to a log, and it is sent back exactly as it came. Once the student taps confirm the card lets go of it.
// An expired or reused token comes back from the server as a normal reply that says nothing was sent,
// so the card never decides that on its own: after the time runs out it says so and still lets the server answer.
import { el, errorText, label } from "../dom.js";
import { STRINGS } from "../i18n.js";
import { routeBlocked } from "../routes.js";
import { showRunnerUp, triggerKeys } from "../council.js";

export function confirmationCard(ctx, confirmation, onConfirm) {
  let token = confirmation.confirmation_token;
  const warningKey = Object.hasOwn(STRINGS.en, confirmation.warning_key) ? confirmation.warning_key : "warn_unknown";
  const button = label(ctx, "button", "confirm_button", null, { type: "button", class: "btn btn-primary confirm-button" });
  const expiry = el("p", { class: "hint confirm-expiry", "aria-live": "polite" });
  const status = el("p", { class: "hint confirm-status", "aria-live": "polite" });
  const error = el("p", { class: "error confirm-error", role: "alert" });

  const seconds = Number(confirmation.expires_in_seconds) > 0 ? Number(confirmation.expires_in_seconds) : 300;
  const deadline = Date.now() + seconds * 1000;
  function tick() {
    const left = Math.ceil((deadline - Date.now()) / 1000);
    if (left > 0) {
      expiry.replaceChildren(label(ctx, "span", "expires_in", { seconds: left }));
    } else {
      expiry.replaceChildren(label(ctx, "span", "maybe_expired"));
      clearInterval(timer);
    }
  }
  const timer = setInterval(tick, 1000);
  tick();

  button.addEventListener("click", async () => {
    if (token === null) return;
    const sending = token;
    token = null;
    button.disabled = true;
    error.replaceChildren();
    status.replaceChildren(label(ctx, "span", "confirming"));
    try {
      await onConfirm(sending);
      clearInterval(timer);
      expiry.replaceChildren();
      status.replaceChildren(label(ctx, "span", "confirm_sent"));
    } catch (failure) {
      // The server did not answer, so the student may try again. A token it already used is refused there under R10.
      token = sending;
      button.disabled = false;
      status.replaceChildren();
      error.textContent = errorText(ctx, failure);
    }
  });

  return el(
    "div",
    { class: "card card-warn confirm-card" },
    label(ctx, "h3", "confirm_title"),
    label(ctx, "p", warningKey, null, { class: "confirm-warning" }),
    actionFacts(ctx, confirmation.action),
    confirmation.routes?.length ? routeList(ctx, confirmation.routes, confirmation.selected_route) : null,
    confirmation.council ? councilAdvice(ctx, confirmation.council) : null,
    expiry,
    button,
    status,
    error,
  );

}

function typeName(ctx, type) {
  const key = `type_${type}`;
  return Object.hasOwn(STRINGS.en, key) ? label(ctx, "span", key) : type;
}

function actionFacts(ctx, action) {
  const rows = [];
  const add = (key, value) => {
    if (value === null || value === undefined || value === "") return;
    rows.push(label(ctx, "dt", key), el("dd", {}, value));
  };
  add("field_type", typeName(ctx, action.type));
  if (action.amount !== null && action.amount !== undefined) add("field_amount", `${action.amount} ${action.currency ?? ""}`.trim());
  add("field_payee", action.payee_id);
  add("field_corridor", action.corridor);
  add("field_purpose", action.purpose);
  add("field_card", action.instrument_id);
  add("field_receipt", action.receipt_id ?? action.cancel_of);
  for (const extra of ["standing_terms", "plan_update", "withdrawal_date", "standing_mandate_id"]) {
    const value = action[extra];
    if (value !== null && value !== undefined) {
      rows.push(el("dt", {}, extra), el("dd", { class: "mono" }, typeof value === "string" ? value : JSON.stringify(value)));
    }
  }
  return el("dl", { class: "facts" }, rows);
}

function sameRoute(route, selected) {
  return Boolean(selected) && route.rail === selected.rail && route.corridor === selected.corridor && route.amount === selected.amount;
}

function routeList(ctx, routes, selected) {
  return el(
    "div",
    {},
    label(ctx, "h3", "routes_title"),
    el(
      "ul",
      { class: "routes" },
      routes.map((route) => {
        const chosen = sameRoute(route, selected);
        return el(
          "li",
          { class: chosen ? "selected" : null, "data-rail": route.rail },
          el("strong", {}, route.rail),
          " ",
          chosen ? label(ctx, "span", "route_selected", null, { class: "badge" }) : null,
          " ",
          route.simulated ? label(ctx, "span", "route_simulated", null, { class: "badge" }) : null,
          " ",
          routeBlocked(route) ? label(ctx, "span", "route_blocked", null, { class: "badge route-blocked" }) : null,
          el(
            "div",
            {},
            label(ctx, "span", "route_fee", {
              fee: route.fee,
              spread: route.spread_cost,
              currency: route.currency_from,
              hours: route.arrival_hours,
            }),
          ),
          route.blocked_reason ? el("div", { class: "hint" }, route.blocked_reason) : null,
          // The knowledge entry the route cites, exactly as the server names it. The app keeps no copy of the entries.
          route.rule_id ? label(ctx, "div", "route_source", { id: route.rule_id }, { class: "hint mono route-source" }) : null,
        );
      }),
    ),
  );
}

function councilAdvice(ctx, council) {
  const triggers = triggerKeys(council.triggers);
  return el(
    "div",
    { class: "council" },
    label(ctx, "h3", "council_title"),
    label(ctx, "p", "council_chosen", { rail: council.chosen }),
    // Only above the threshold, as the reply text does (src/council.js).
    showRunnerUp(council) ? label(ctx, "p", "council_runner_up", { rail: council.runner_up }, { class: "council-runner-up" }) : null,
    el("p", { class: "council-reason" }, council.reason),
    label(ctx, "p", "council_disagreement", { score: council.disagreement }, { class: "hint" }),
    triggers.length
      ? el("div", { class: "council-triggers" }, label(ctx, "p", "council_triggers", null, { class: "hint" }), el("ul", {}, triggers.map((key) => label(ctx, "li", key))))
      : null,
  );
}
