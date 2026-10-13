import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { BLOCKED_ORIGINS, BLOCKED_ENDINGS, TURN_MARKERS, splitReply } from "../../src/reply-text.js";

test("the documented refused paste splits into the blocked sentence, the model's words and the turn line", () => {
  const text =
    "Text you pasted asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action. I cannot do that. Rules: R01. This action came from pasted_text, which is data and never an instruction. Only the user's own turn can ask for an action. This turn: a transfer: refused under R01.";
  assert.deepEqual(splitReply(text, "en"), {
    blocked: ["Text you pasted asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action."],
    body: "I cannot do that. Rules: R01. This action came from pasted_text, which is data and never an instruction. Only the user's own turn can ask for an action.",
    turn: "This turn: a transfer: refused under R01.",
  });
});

test("a reply with no blocked request has no top sentence", () => {
  const text = "That confirmation was not found, so nothing was sent. This turn: a confirmation: not accepted, so nothing was done.";
  assert.deepEqual(splitReply(text, "en"), {
    blocked: [],
    body: "That confirmation was not found, so nothing was sent.",
    turn: "This turn: a confirmation: not accepted, so nothing was done.",
  });
});

test("Portuguese and Chinese markers are found", () => {
  const pt = splitReply(
    "O texto que você colou pediu ao Lifeline para fazer um pagamento, e o Lifeline não fez isso, porque só as suas próprias palavras podem iniciar uma ação. Não posso. Neste turno: uma transferência: recusada sob R01.",
    "pt",
  );
  assert.equal(pt.blocked.length, 1);
  assert.equal(pt.body, "Não posso.");
  assert.equal(pt.turn, "Neste turno: uma transferência: recusada sob R01.");
  const zh = splitReply("你粘贴的文字要求 Lifeline 付一笔款，Lifeline 没有这样做，因为只有你自己的话才能发起操作。 我不能这样做。 本轮：没有提出、更改或发送任何内容。", "zh");
  assert.deepEqual(zh.blocked, ["你粘贴的文字要求 Lifeline 付一笔款，Lifeline 没有这样做，因为只有你自己的话才能发起操作。"]);
  assert.equal(zh.body, "我不能这样做。");
  assert.equal(zh.turn, "本轮：没有提出、更改或发送任何内容。");
});

test("several blocked requests each get their own top line, from a paste and from data Lifeline read", () => {
  const text =
    "Text you pasted asked Lifeline to add a payee, and Lifeline did not do it, because only your own words can start an action. Information Lifeline read asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action. Done. This turn: nothing was proposed, changed or sent.";
  const parts = splitReply(text, "en");
  assert.equal(parts.blocked.length, 2);
  assert.ok(parts.blocked[1].startsWith("Information Lifeline read"));
  assert.equal(parts.body, "Done.");
});

test("the model writing 'This turn:' earlier does not move the line: the code's sentence is always the last one", () => {
  const parts = splitReply("This turn: I sent everything! This turn: nothing was proposed, changed or sent.", "en");
  assert.equal(parts.body, "This turn: I sent everything!");
  assert.equal(parts.turn, "This turn: nothing was proposed, changed or sent.");
});

test("a sentence like the blocked one in the middle of the model's words is left in the body", () => {
  const text = "Hello. Text you pasted asked Lifeline to pay, and Lifeline did not do it, because only your own words can start an action. This turn: nothing was proposed, changed or sent.";
  assert.deepEqual(splitReply(text, "en").blocked, []);
});

test("a reply in a language the app has no marker for still finds a known marker, or leaves the text whole", () => {
  assert.equal(splitReply("Hola. This turn: nothing was proposed, changed or sent.", "es").turn, "This turn: nothing was proposed, changed or sent.");
  assert.deepEqual(splitReply("Just words.", "en"), { blocked: [], body: "Just words.", turn: null });
});

test("a reply that is only the two code sentences has an empty body", () => {
  assert.deepEqual(splitReply("This turn: nothing was proposed, changed or sent.", "en"), {
    blocked: [],
    body: "",
    turn: "This turn: nothing was proposed, changed or sent.",
  });
});

// The markers are copied from the backend. If lane A changes the wording, this fails before the app silently stops splitting.
test("every marker the app looks for is still written by core/agent.py", () => {
  const agent = readFileSync(new URL("../../../core/agent.py", import.meta.url), "utf-8");
  for (const marker of Object.values(TURN_MARKERS)) assert.ok(agent.includes(`"${marker}{items}`) || agent.includes(`"${marker} {items}`), marker);
  for (const origins of Object.values(BLOCKED_ORIGINS)) for (const origin of origins) assert.ok(agent.includes(`"${origin}"`), origin);
  for (const ending of Object.values(BLOCKED_ENDINGS)) assert.ok(agent.includes(`${ending}"`), ending);
});

import { partsOf } from "../../src/reply-text.js";

const PASTED_TEXT =
  "Text you pasted asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action. I cannot do that. Rules: R01. This turn: a transfer: refused under R01.";

test("with the fields present, blocked and turn_summary are read from the fields and cut from the body", () => {
  const parts = partsOf({
    text: PASTED_TEXT,
    lang: "en",
    blocked: ["Text you pasted asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action."],
    turn_summary: "This turn: a transfer: refused under R01.",
  });
  assert.deepEqual(parts, {
    blocked: ["Text you pasted asked Lifeline to make a payment, and Lifeline did not do it, because only your own words can start an action."],
    body: "I cannot do that. Rules: R01.",
    turn: "This turn: a transfer: refused under R01.",
    from: { blocked: "field", turn: "field" },
  });
});

test("the fields win over the wording: a sentence that only looks like the code's stays in the body", () => {
  const parts = partsOf({
    text: "Text you pasted asked Lifeline to pay, and Lifeline did not do it, because only your own words can start an action. This turn: I sent it! This turn: nothing was proposed, changed or sent.",
    lang: "en",
    blocked: [],
    turn_summary: "This turn: nothing was proposed, changed or sent.",
  });
  assert.deepEqual(parts.blocked, []);
  assert.equal(parts.body, "Text you pasted asked Lifeline to pay, and Lifeline did not do it, because only your own words can start an action. This turn: I sent it!");
  assert.equal(parts.turn, "This turn: nothing was proposed, changed or sent.");
});

test("a field in a language the app has no wording for still works", () => {
  const parts = partsOf({ text: "Hola. Este turno: nada.", lang: "es", blocked: [], turn_summary: "Este turno: nada." });
  assert.equal(parts.body, "Hola.");
  assert.equal(parts.turn, "Este turno: nada.");
});

test("turn_summary null means no turn line, and the wording is not searched for one", () => {
  const parts = partsOf({ text: "Hello. This turn: nothing was proposed, changed or sent.", lang: "en", blocked: [], turn_summary: null });
  assert.equal(parts.turn, null);
  assert.equal(parts.body, "Hello. This turn: nothing was proposed, changed or sent.");
  assert.equal(parts.from.turn, "field");
});

test("a field sentence that is not where text should have it is still shown, and text is left whole rather than cut wrongly", () => {
  const parts = partsOf({ text: "Hello there.", lang: "en", blocked: ["A blocked sentence."], turn_summary: "This turn: nothing was proposed, changed or sent." });
  assert.deepEqual(parts.blocked, ["A blocked sentence."]);
  assert.equal(parts.turn, "This turn: nothing was proposed, changed or sent.");
  assert.equal(parts.body, "Hello there.");
});

test("without the fields, an older reply falls back to the wording match", () => {
  const parts = partsOf({ text: PASTED_TEXT, lang: "en" });
  assert.equal(parts.blocked.length, 1);
  assert.equal(parts.body, "I cannot do that. Rules: R01.");
  assert.equal(parts.turn, "This turn: a transfer: refused under R01.");
  assert.deepEqual(parts.from, { blocked: "wording", turn: "wording" });
});

test("each field falls back on its own when only the other is present", () => {
  const onlyTurn = partsOf({ text: PASTED_TEXT, lang: "en", turn_summary: "This turn: a transfer: refused under R01." });
  assert.deepEqual(onlyTurn.from, { blocked: "wording", turn: "field" });
  assert.equal(onlyTurn.blocked.length, 1);
  assert.equal(onlyTurn.body, "I cannot do that. Rules: R01.");
  const onlyBlocked = partsOf({ text: PASTED_TEXT, lang: "en", blocked: [] });
  assert.deepEqual(onlyBlocked.from, { blocked: "field", turn: "wording" });
  assert.deepEqual(onlyBlocked.blocked, []);
  assert.equal(onlyBlocked.turn, "This turn: a transfer: refused under R01.");
});
