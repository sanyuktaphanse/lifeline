// What the onboarding asks and what it does with the answers.
//
// The trip stays in page memory only: nothing is sent and nothing is written to browser storage.
// The safety net collects nothing it cannot keep. Four of its steps are the four fields update_plan changes at
// tier 1 (PLAN_UPDATE_FIELDS in contracts/schemas.py); they end in one chat message the student reads and sends
// through /chat, where the engine checks it like any other request and the ledger records the change. The trusted
// contact, the emergency money and the safety question are read only: chat cannot change them, so the app does not
// ask for them.
import { t } from "./i18n.js";

export const PURPOSES = ["exchange", "degree", "internship", "leisure", "family", "work"];

// Source: PLAN_UPDATE_FIELDS in contracts/schemas.py; tests/unit/onboarding.test.js compares them.
export const UPDATABLE_FIELDS = ["backup_instrument", "backup_route", "wallet_token_present", "cash_plan"];
export const PLAN_STEPS = ["backup_card", "backup_route", "wallet", "cash_plan", "contact", "money", "question"];
export const READ_ONLY_STEPS = new Set(["contact", "money", "question"]);

// fixture: the plan in fixtures/demo_user.yaml, which the server loads and the live rescue reads.
export const SAMPLE_PLAN = {
  cards: [
    { name: "Wise debit card", instrument_id: "wise:card_01" },
    { name: "Revolut card", instrument_id: "revolut:card_02" },
  ],
  primary_instrument: "wise:card_01",
  backup_instrument: "revolut:card_02",
  backup_route: "wise",
  wallet_token_present: true,
  cash_plan: ["sg_cash_pickup_001"],
  trusted_contact: { name: "Ana", channel: "whatsapp" },
  emergency_allowance: "300",
  currency: "SGD",
  question: "What are the last four characters of your student pass number?",
};

// Routes rails/fake_router.py quotes that are not simulated. The plan stores the backup route as text.
export const ROUTE_CHOICES = ["wise", "bank_wire"];

// The cash plan holds knowledge entry ids only (_update_plan in core/agent.py). sg_cash_pickup_001 is the one cash
// entry rails/knowledge has; the other choice is an empty plan.
export const CASH_CHOICES = [
  { id: "pickup", ids: ["sg_cash_pickup_001"] },
  { id: "none", ids: [] },
];

export function tripReady(trip) {
  return Boolean(trip?.home && trip?.study && PURPOSES.includes(trip.purpose));
}

// Source: core/agent.py, _update_plan, and Plan in contracts/schemas.py: a backup is one of the plan's own cards
// and never the primary.
export function backupChoices(plan) {
  return plan.cards.filter((card) => card.instrument_id !== plan.primary_instrument);
}

// The plan the server holds: the sample plan with each update the ledger executed, in order. The server rebuilds
// its plan from the ledger the same way after a restart (tests/test_plan_update.py).
export function planOnFile(entries) {
  const plan = structuredClone(SAMPLE_PLAN);
  for (const entry of entries ?? []) {
    const updated = entry.kind === "execution" ? entry.payload?.result?.plan_updated : null;
    if (!updated) continue;
    for (const name of UPDATABLE_FIELDS) if (Object.hasOwn(updated, name)) plan[name] = structuredClone(updated[name]);
  }
  return plan;
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function planChanges(onFile, chosen) {
  const changes = {};
  for (const name of UPDATABLE_FIELDS) {
    if (Object.hasOwn(chosen, name) && !same(chosen[name], onFile[name])) changes[name] = structuredClone(chosen[name]);
  }
  return changes;
}

// One message in the student's language, naming each change in plain words with the id the plan holds, so the
// words the engine checks carry every value. Null when nothing changed.
export function composeMessage(lang, changes, plan) {
  const parts = [];
  if ("backup_instrument" in changes) {
    const card = plan.cards.find((item) => item.instrument_id === changes.backup_instrument);
    parts.push(t(lang, "msg_backup_card", { name: card?.name ?? changes.backup_instrument, id: changes.backup_instrument }));
  }
  if ("backup_route" in changes) parts.push(t(lang, "msg_backup_route", { name: t(lang, `rail_${changes.backup_route}`), rail: changes.backup_route }));
  if ("wallet_token_present" in changes) parts.push(t(lang, changes.wallet_token_present ? "msg_wallet_yes" : "msg_wallet_no"));
  if ("cash_plan" in changes) parts.push(t(lang, changes.cash_plan.length ? "msg_cash_pickup" : "msg_cash_none"));
  return parts.length ? t(lang, "msg_plan_update", { parts: parts.join(t(lang, "msg_join")) }) : null;
}

export const ONBOARDING_KEYS = [
  "open_me", "onb_trip_title", "onb_trip_intro", "onb_home", "onb_study", "onb_choose_country", "onb_group_on_file",
  "onb_group_others", "onb_no_rules", "onb_purpose", ...PURPOSES.map((id) => `purpose_${id}`), "onb_continue", "onb_skip",
  "onb_skip_note", "onb_back", "onb_next", "onb_step_n", "onb_plan_title", "onb_plan_intro", "onb_on_file",
  "onb_backup_card_q", "onb_backup_card_hint", "onb_backup_route_q", "onb_backup_route_hint", "onb_wallet_q",
  "onb_wallet_yes", "onb_wallet_no", "onb_cash_q", "onb_cash_pickup", "onb_cash_none", "onb_contact_title",
  "onb_contact_ro", "onb_contact_why", "onb_money_title", "onb_money_ro", "onb_money_why", "onb_question_title",
  "onb_question_ro", "onb_question_why", "onb_rescue_note", "onb_message_title", "onb_message_intro",
  "onb_message_none", "onb_put_in_chat", "onb_done", "msg_plan_update", "msg_join", "msg_backup_card",
  "msg_backup_route", "msg_wallet_yes", "msg_wallet_no", "msg_cash_pickup", "msg_cash_none", "rail_wise",
  "rail_bank_wire", "rail_sim_pix", "channel_whatsapp", "channel_wechat", "channel_telegram", "channel_sms",
  "channel_phone_call", "channel_email", "hello_study", "hello_plain", "from_home", "from_home_plain",
  "starter_home_cn", "starter_home_in", "starter_home_br", "starter_home_other", "me_title", "me_trip", "me_no_trip",
  "me_trip_line", "me_change", "me_net", "me_sample", "me_sample_note", "me_card", "me_backup_card",
  "me_backup_route", "me_wallet", "me_cash", "me_yes", "me_no", "me_none", "sample_question", "me_question", "me_contact", "me_contact_line", "me_money", "me_routes",
  "me_route_rule", "me_checks", "me_check_intro", "me_check_button", "check_remit_from_china",
  "check_arrive_in_china", "check_enable_pix", "me_check_none", "me_check_documents", "me_check_triggers",
  "me_check_sources", "me_check_not_ready", "me_signin", "me_coming_soon", "me_close", "route_source",
];
