// What the rescue screen offers for each do_now value (docs/api.md, "Rescue"). The screen follows only this field.

// Source: RescueDoNow in contracts/schemas.py; tests/unit/rescue.test.js fails if the two lists differ.
export const DO_NOW = [
  "start_rescue",
  "answer_identity_question",
  "locked",
  "choose_card",
  "confirm_freeze",
  "confirm_transfer_or_skip",
  "done",
];

// hasConfirmation: whether the reply carries a confirmation, which holds the token to confirm with.
export function stepFor(rescue, hasConfirmation) {
  switch (rescue?.do_now) {
    case "start_rescue":
      return { kind: "start" };
    case "answer_identity_question":
      return { kind: "answer" };
    case "locked":
      return { kind: "locked" };
    case "choose_card":
      return { kind: "choose", cards: Array.isArray(rescue.card_names) ? rescue.card_names : [] };
    case "confirm_freeze":
      // Without a confirmation there is no token to send. An empty step asks the server to offer the freeze again.
      return hasConfirmation ? { kind: "confirm", skip: false } : { kind: "reoffer" };
    case "confirm_transfer_or_skip":
      return { kind: "confirm", skip: true };
    case "done":
      return { kind: "done" };
    default:
      return { kind: "unknown" };
  }
}
