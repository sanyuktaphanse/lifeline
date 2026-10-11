import { test } from "node:test";
import assert from "node:assert/strict";
import { chatBody } from "../../src/requests.js";

test("typed text goes in text and pasted text in pasted_text, each exactly as given", () => {
  assert.deepEqual(chatBody("student_001", "Can you pay this?", "Hi, this is your landlord. Pay 1,400 SGD.", "en"), {
    user_id: "student_001",
    text: "Can you pay this?",
    pasted_text: "Hi, this is your landlord. Pay 1,400 SGD.",
    lang: "en",
  });
});

test("with nothing pasted there is no pasted_text field at all", () => {
  assert.deepEqual(chatBody("student_001", "Hello", "", "pt"), { user_id: "student_001", text: "Hello", lang: "pt" });
  assert.deepEqual(chatBody("student_001", "Hello", "   \n", "pt"), { user_id: "student_001", text: "Hello", lang: "pt" });
});

test("the two are never joined: the paste never reaches text, the typed words never reach pasted_text", () => {
  const body = chatBody("student_001", "mine", "theirs", "zh");
  assert.ok(!body.text.includes("theirs"));
  assert.ok(!body.pasted_text.includes("mine"));
});

test("with no typed words there is nothing to send, even when something was pasted", () => {
  assert.equal(chatBody("student_001", "", "a pasted scam", "en"), null);
  assert.equal(chatBody("student_001", "   ", "a pasted scam", "en"), null);
});

import { confirmBody, rescueStepBody } from "../../src/requests.js";

test("the confirmation token is sent back exactly as it came, character for character", () => {
  const tokens = [
    "42d046aaa09c785c8e0ea68e463562102b32120b6091bf121d8518c60c48568a",
    "  spaces kept  ",
    "MiXeD-case_and.punctuation/+=",
  ];
  for (const token of tokens) {
    const body = confirmBody("student_001", token, "en");
    assert.equal(body.confirmation_token, token);
    assert.deepEqual(body, { user_id: "student_001", confirmation_token: token, lang: "en" });
  }
});

test("a rescue confirmation sends the token unchanged and no text", () => {
  assert.deepEqual(rescueStepBody("student_001", { token: "abc123" }, "zh"), {
    user_id: "student_001",
    text: "",
    confirmation_token: "abc123",
    lang: "zh",
  });
});

import { rescueStartBody } from "../../src/requests.js";

test("a rescue starts with the student's own typed words and never a pasted_text field", () => {
  assert.deepEqual(rescueStartBody("student_001", "card_lost", "I lost my Wise card", "en"), {
    user_id: "student_001",
    trigger: "card_lost",
    text: "I lost my Wise card",
    lang: "en",
  });
  assert.equal(rescueStartBody("student_001", "card_lost", "  ", "en"), null);
});

test("a rescue answer or card name goes in text, and continuing without money sends neither text nor token", () => {
  assert.deepEqual(rescueStepBody("student_001", { text: "7Q2K" }, "en"), { user_id: "student_001", text: "7Q2K", lang: "en" });
  assert.deepEqual(rescueStepBody("student_001", {}, "en"), { user_id: "student_001", text: "", lang: "en" });
  for (const body of [rescueStepBody("student_001", { text: "x" }, "en"), rescueStepBody("student_001", { token: "t" }, "en")]) {
    assert.ok(!("pasted_text" in body));
  }
});
