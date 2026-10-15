// What the onboarding asks and what it keeps. Everything here lives in page memory only: nothing is sent to the
// server and nothing is written to browser storage, so closing the page forgets it. The live rescue always reads
// the demo student's plan in fixtures/demo_user.yaml, which SAMPLE_PLAN repeats for the screen.

export const PURPOSES = ["exchange", "degree", "internship", "leisure", "family", "work"];
export const PLAN_STEPS = ["card", "backup", "question", "contact", "money"];

// Common choices for students, in no order of merit. Lifeline recommends none of them and is paid by none.
const CARDS = [
  { id: "wise", name: "Wise" },
  { id: "revolut", name: "Revolut" },
  { id: "youtrip", name: "YouTrip", singapore: true },
  { id: "dbs_posb", name: "DBS / POSB", singapore: true },
  { id: "ocbc", name: "OCBC", singapore: true },
  { id: "uob", name: "UOB", singapore: true },
  { id: "home_card", key: "card_home" },
  { id: "unsure", key: "card_unsure" },
];

// The Singapore cards are offered for study in Singapore, and when no trip was given, as the demo student banks there.
export function cardChoices(trip) {
  const inSingapore = !trip?.study || trip.study === "SG";
  return CARDS.filter((card) => inSingapore || !card.singapore);
}

// The first is the demo plan's question (fixtures/demo_user.yaml); the other two are common alternatives.
export const SAFETY_QUESTIONS = ["safety_q_pass", "safety_q_school", "safety_q_street"];
export const RELATIONSHIPS = ["parent", "sibling", "partner", "relative", "friend", "other"];
export const CHANNELS = ["whatsapp", "wechat", "telegram", "sms", "phone_call", "email"];

// Fixture: fixtures/demo_user.yaml sets emergency_allowance to 300 SGD; 100 and 200 are smaller amounts a student may
// prefer. They are choices shown on this page, never a limit, and the page sends none of them.
export const EMERGENCY_CHOICES = ["100", "200", "300", "none"];

// fixture: the plan in fixtures/demo_user.yaml, which the live rescue reads. tests/unit/onboarding.test.js compares them.
export const SAMPLE_PLAN = {
  cards: ["Wise debit card", "Revolut card"],
  question: "What are the last four characters of your student pass number?",
  contact: { name: "Ana", channel: "whatsapp" },
  money: "300",
  currency: "SGD",
};

export function tripReady(trip) {
  return Boolean(trip?.home && trip?.study && PURPOSES.includes(trip.purpose));
}

export function stepReady(step, draft) {
  switch (step) {
    case "card":
      return CARDS.some((card) => card.id === draft.card);
    case "backup":
      return typeof draft.backup === "boolean";
    case "question":
      return SAFETY_QUESTIONS.includes(draft.question) && draft.answerSet === true;
    case "contact":
      return Boolean(draft.contact?.name?.trim()) && RELATIONSHIPS.includes(draft.contact.relationship) && CHANNELS.includes(draft.contact.channel);
    case "money":
      return EMERGENCY_CHOICES.includes(draft.money);
    default:
      return false;
  }
}

// Only whether an answer was typed is kept. The words themselves are dropped here and never stored.
export function setAnswer(draft, typed) {
  return { ...draft, answerSet: typeof typed === "string" && typed.trim() !== "" };
}

// Source: docs/decisions.md, 8 October 2026, item 4: a trusted contact holds a name and a channel only.
export function planContact(contact) {
  return { name: contact.name.trim(), channel: contact.channel };
}

export const ONBOARDING_KEYS = [
  "open_me", "onb_trip_title", "onb_trip_intro", "onb_home", "onb_study", "onb_choose_country", "onb_group_on_file",
  "onb_group_others", "onb_no_rules", "onb_purpose", ...PURPOSES.map((id) => `purpose_${id}`), "onb_continue", "onb_skip",
  "onb_skip_note", "onb_back", "onb_next", "onb_step_n", "onb_plan_title", "onb_card_q", "onb_card_common", "onb_card_note",
  "card_home", "card_unsure", "onb_unsure_1", "onb_unsure_2", "onb_backup_q", "onb_backup_hint", "onb_yes", "onb_no",
  "onb_question_q", ...SAFETY_QUESTIONS, "onb_answer", "onb_answer_note", "onb_rescue_note", "onb_contact_q",
  "onb_contact_name", "onb_contact_rel", ...RELATIONSHIPS.map((id) => `rel_${id}`), "onb_contact_phone",
  "onb_contact_email", "onb_contact_channel", ...CHANNELS.map((id) => `channel_${id}`), "onb_on_device", "onb_money_q",
  "onb_money_hint", "onb_money_amount", "onb_money_none", "onb_done_title", "onb_done", "onb_nothing_sent",
  "hello_study", "hello_plain", "from_home", "from_home_plain", "starter_home_cn", "starter_home_in", "starter_home_br",
  "starter_home_other", "me_title", "me_trip", "me_no_trip", "me_trip_line", "me_change", "me_net", "me_sample",
  "me_sample_note", "me_card", "me_backup", "me_question", "me_question_set", "me_contact", "me_contact_line",
  "me_on_device", "me_money", "me_routes", "me_route_rule", "me_checks", "me_check_intro", "me_check_button",
  "check_remit_from_china", "check_arrive_in_china", "check_enable_pix", "me_check_none", "me_check_documents",
  "me_check_triggers", "me_check_sources", "me_check_not_ready", "me_signin", "me_coming_soon", "me_close", "route_source",
];
