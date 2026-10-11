import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DO_NOW, stepFor } from "../../src/rescue-steps.js";

test("the app has a step for every do_now value the backend can send, and no other", () => {
  const schemas = readFileSync(new URL("../../../contracts/schemas.py", import.meta.url), "utf-8");
  const block = schemas.slice(schemas.indexOf("RescueDoNow = Literal["), schemas.indexOf("]", schemas.indexOf("RescueDoNow = Literal[")));
  const backend = [...block.matchAll(/"(\w+)"/g)].map((match) => match[1]).sort();
  assert.deepEqual([...DO_NOW].sort(), backend);
});

test("each do_now names what the student can do", () => {
  assert.deepEqual(stepFor({ do_now: "answer_identity_question" }, false), { kind: "answer" });
  assert.deepEqual(stepFor({ do_now: "locked" }, false), { kind: "locked" });
  assert.deepEqual(stepFor({ do_now: "choose_card", card_names: ["A", "B"] }, false), { kind: "choose", cards: ["A", "B"] });
  assert.deepEqual(stepFor({ do_now: "confirm_freeze" }, true), { kind: "confirm", skip: false });
  assert.deepEqual(stepFor({ do_now: "confirm_freeze" }, false), { kind: "reoffer" });
  assert.deepEqual(stepFor({ do_now: "confirm_transfer_or_skip" }, true), { kind: "confirm", skip: true });
  assert.deepEqual(stepFor({ do_now: "confirm_transfer_or_skip" }, false), { kind: "confirm", skip: true });
  assert.deepEqual(stepFor({ do_now: "done" }, false), { kind: "done" });
  assert.deepEqual(stepFor({ do_now: "start_rescue" }, false), { kind: "start" });
});

test("a do_now the app does not know shows the reply and offers nothing, rather than guessing", () => {
  assert.deepEqual(stepFor({ do_now: "something_new" }, false), { kind: "unknown" });
});
