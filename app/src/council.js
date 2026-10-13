// What the confirmation card shows from the council's advice (CouncilAdvice in contracts/schemas.py).

// Source: RUNNER_UP_DISAGREEMENT in core/agent.py, decision 2 in docs/decisions.md. The reply text names the
// runner up only above this score, so the card does too; tests/unit/council.test.js fails if the two differ.
export const RUNNER_UP_DISAGREEMENT = 0.4;

// Source: AgentLoop._escalations in core/agent.py, the reasons a transfer is put to the council.
// tests/unit/council.test.js fails if the backend adds, removes or renames one.
export const COUNCIL_TRIGGERS = [
  "above_half_per_txn_limit",
  "first_transfer_on_corridor",
  "first_transfer_to_payee",
  "cost_and_speed_differ",
  "route_degraded_or_down",
  "rescue_state",
];

export function showRunnerUp(council) {
  const score = council?.disagreement;
  return typeof score === "number" && Number.isFinite(score) && score > RUNNER_UP_DISAGREEMENT;
}

// Each trigger as the key of its label. An id the app does not know is left off rather than shown raw.
export function triggerKeys(triggers) {
  return Array.isArray(triggers) ? triggers.filter((id) => COUNCIL_TRIGGERS.includes(id)).map((id) => `trigger_${id}`) : [];
}
