// Splits a reply's text into the two sentences the backend writes in code and the model's words between them.
// docs/api.md, "Reading an AgentReply": when a request from pasted text or from data was blocked, `text` begins
// with one sentence per blocked request; every reply from /chat, /confirm and the rescue ends with one sentence
// of what the call did. The API has no separate field for either, so the wording below is copied from
// core/agent.py, and tests/unit/reply-text.test.js fails if the backend stops writing it.

// Source: core/agent.py, the "turn_summary" and "turn_nothing" texts in each language.
export const TURN_MARKERS = { en: "This turn:", pt: "Neste turno:", zh: "本轮：" };

// Source: core/agent.py, the "injection_from_paste" and "injection_from_data" texts, which begin the sentence.
export const BLOCKED_ORIGINS = {
  en: ["Text you pasted", "Information Lifeline read"],
  pt: ["O texto que você colou", "Uma informação que o Lifeline leu"],
  zh: ["你粘贴的文字", "Lifeline 读取的信息"],
};

// Source: core/agent.py, the end of the "injection_blocked" text, which ends the sentence.
export const BLOCKED_ENDINGS = {
  en: "because only your own words can start an action.",
  pt: "porque só as suas próprias palavras podem iniciar uma ação.",
  zh: "因为只有你自己的话才能发起操作。",
};

function markersFor(lang) {
  const own = TURN_MARKERS[lang];
  return own ? [own, ...Object.values(TURN_MARKERS).filter((marker) => marker !== own)] : Object.values(TURN_MARKERS);
}

// The code's sentence is the last one, so the last marker that starts a sentence is the one to take.
function lastTurnMarker(text, lang) {
  for (const marker of markersFor(lang)) {
    let at = text.lastIndexOf(marker);
    while (at > 0 && !/\s/.test(text[at - 1])) at = text.lastIndexOf(marker, at - 1);
    if (at >= 0) return at;
  }
  return -1;
}

function peelBlocked(text) {
  const blocked = [];
  let rest = text;
  for (;;) {
    let found = null;
    for (const code of Object.keys(BLOCKED_ORIGINS)) {
      if (!BLOCKED_ORIGINS[code].some((origin) => rest.startsWith(origin))) continue;
      const end = rest.indexOf(BLOCKED_ENDINGS[code]);
      if (end >= 0) {
        found = rest.slice(0, end + BLOCKED_ENDINGS[code].length);
        break;
      }
    }
    if (found === null) return { blocked, rest };
    blocked.push(found);
    rest = rest.slice(found.length).trimStart();
  }
}

export function splitReply(text, lang) {
  const whole = typeof text === "string" ? text : "";
  const at = lastTurnMarker(whole, lang);
  const turn = at >= 0 ? whole.slice(at).trim() : null;
  const before = at >= 0 ? whole.slice(0, at) : whole;
  const { blocked, rest } = peelBlocked(before.trim());
  return { blocked, body: rest.trim(), turn };
}
