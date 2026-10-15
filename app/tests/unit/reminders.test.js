import { test } from "node:test";
import assert from "node:assert/strict";
import { reminderItems } from "../../src/reminders.js";

// The example of docs/api.md, GET /reminders/{user_id}.
const DOCUMENTED = {
  user_id: "student_001",
  now: "2026-10-09T00:00:00Z",
  due: [{ text: "Rent is due on 1 October", due: "2026-09-28T00:00:00Z", seq: 15 }],
  upcoming: [{ text: "Renew the student pass", due: "2026-11-02T00:00:00Z", seq: 20 }, { text: "Call home", due: null, seq: 22 }],
};

test("due reminders come first and are counted, then the upcoming ones", () => {
  const { items, dueCount } = reminderItems(DOCUMENTED);
  assert.equal(dueCount, 1);
  assert.deepEqual(items.map((item) => [item.text, item.isDue, item.due]), [
    ["Rent is due on 1 October", true, "2026-09-28T00:00:00Z"],
    ["Renew the student pass", false, "2026-11-02T00:00:00Z"],
    ["Call home", false, null],
  ]);
});

test("a missing list reads as empty", () => {
  assert.deepEqual(reminderItems({}), { items: [], dueCount: 0 });
});
