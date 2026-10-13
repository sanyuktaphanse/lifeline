// Splits a reply into the two sentences the backend writes in code and the model's words between them.
// docs/api.md, "Reading an AgentReply": when a request from pasted text or from data was blocked, `text` begins
// with one sentence per blocked request; every reply from /chat, /confirm and the rescue ends with one sentence
// of what the call did. The reply carries both as fields, `blocked` and `turn_summary`, and partsOf reads them.
// Only when a field is absent, as on a server from before the fields, is the sentence found by its wording,
// which is copied below from core/agent.py; tests/unit/reply-text.test.js fails if the backend stops writing it.

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

// Reads the two code written sentences from the reply's fields, each field on its own, and cuts them from `text`
// to leave the model's words. A field sentence is cut only where `text` has it, at the start or the end; if it is
// not there, `text` is left whole, so nothing the student should read is lost. `from` says where each part came from.
export function partsOf(reply) {
  const text = typeof reply?.text === "string" ? reply.text : "";
  const hasBlocked = Array.isArray(reply?.blocked);
  const hasTurn = reply !== null && typeof reply === "object" && "turn_summary" in reply;
  const wording = hasBlocked && hasTurn ? null : splitReply(text, reply?.lang);

  let body = text;
  let turn;
  if (hasTurn) {
    turn = typeof reply.turn_summary === "string" && reply.turn_summary !== "" ? reply.turn_summary : null;
    if (turn !== null && body.trimEnd().endsWith(turn)) body = body.trimEnd().slice(0, -turn.length);
  } else {
    turn = wording.turn;
    if (turn !== null) body = body.slice(0, body.lastIndexOf(turn));
  }

  let blocked;
  body = body.trim();
  if (hasBlocked) {
    blocked = reply.blocked.filter((sentence) => typeof sentence === "string" && sentence !== "");
    for (const sentence of blocked) {
      if (!body.startsWith(sentence)) break;
      body = body.slice(sentence.length).trimStart();
    }
  } else {
    blocked = wording.blocked;
    for (const sentence of blocked) body = body.slice(sentence.length).trimStart();
  }

  return { blocked, body: body.trim(), turn, from: { blocked: hasBlocked ? "field" : "wording", turn: hasTurn ? "field" : "wording" } };
}
