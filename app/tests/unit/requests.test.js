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
