// What the welcome screen and the Guide tab show, as label keys in src/i18n.js. Every sentence says what main does
// today: the facts come from docs/technical_documentation.md and docs/self_assessment.md, and nothing is promised.

export const WELCOME_CARDS = [
  { id: "does", title: "welcome_does_title", lines: ["welcome_does_1", "welcome_does_2"] },
  { id: "never", title: "welcome_never_title", lines: ["welcome_never_1", "welcome_never_2", "welcome_never_3", "welcome_never_4"] },
  { id: "how", title: "welcome_how_title", lines: ["welcome_how_1", "welcome_how_2", "welcome_how_3"] },
];

// Examples are words she can tap to put into the message box. They never go into the paste box.
export const GUIDE_SECTIONS = [
  { id: "rent", title: "guide_rent_title", lines: ["guide_rent_1", "guide_rent_2", "guide_rent_3", "guide_rent_4"], examples: ["guide_ex_rent"] },
  { id: "message", title: "guide_message_title", lines: ["guide_message_1", "guide_message_2", "guide_message_3"], examples: ["guide_ex_message"] },
  { id: "card", title: "guide_card_title", lines: ["guide_card_1", "guide_card_2", "guide_card_3", "guide_card_4"] },
  { id: "china", title: "guide_china_title", lines: ["guide_china_1", "guide_china_2", "guide_china_3"], examples: ["guide_ex_china_1", "guide_ex_china_2"] },
  { id: "india_brazil", title: "guide_inbr_title", lines: ["guide_inbr_1", "guide_inbr_2", "guide_inbr_3"] },
  { id: "ledger", title: "guide_ledger_title", lines: ["guide_ledger_1", "guide_ledger_2", "guide_ledger_3", "guide_ledger_4"] },
];

export const PROTECT_SECTIONS = [
  { id: "decides", title: "protect_decides_title", lines: ["protect_decides_1", "protect_decides_2"] },
  { id: "confirm", title: "protect_confirm_title", lines: ["protect_confirm_1", "protect_confirm_2"] },
  { id: "never", title: "protect_never_title", lines: ["protect_never_1", "protect_never_2"] },
  { id: "recorded", title: "protect_recorded_title", lines: ["protect_recorded_1", "protect_recorded_2", "protect_recorded_3"] },
  { id: "not", title: "protect_not_title", lines: ["protect_not_1"] },
  { id: "demo", title: "protect_demo_title", lines: ["protect_demo_1", "protect_demo_2"] },
];

const OTHER_KEYS = [
  "open_welcome",
  "tab_guide",
  "welcome_tagline",
  "welcome_next",
  "welcome_card_n",
  "welcome_continue",
  "welcome_demo_note",
  "guide_intro",
  "guide_try",
  "guide_protect_title",
  "guide_verify_title",
];

export const NEW_KEYS = [
  ...OTHER_KEYS,
  ...WELCOME_CARDS.flatMap((card) => [card.title, ...card.lines]),
  ...[...GUIDE_SECTIONS, ...PROTECT_SECTIONS].flatMap((section) => [section.title, ...section.lines, ...(section.examples ?? [])]),
];
