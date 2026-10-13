import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { COUNCIL_TRIGGERS, RUNNER_UP_DISAGREEMENT, showRunnerUp, triggerKeys } from "../../src/council.js";
import { STRINGS } from "../../src/i18n.js";

const AGENT = readFileSync(new URL("../../../core/agent.py", import.meta.url), "utf-8");

test("the runner up shows only when the disagreement is above 0.4, never at or below it", () => {
  assert.equal(showRunnerUp({ disagreement: 0 }), false);
  assert.equal(showRunnerUp({ disagreement: 0.39 }), false);
  assert.equal(showRunnerUp({ disagreement: 0.4 }), false);
  assert.equal(showRunnerUp({ disagreement: 0.41 }), true);
  assert.equal(showRunnerUp({ disagreement: 1 }), true);
});

test("a missing or broken disagreement score never shows the runner up", () => {
  assert.equal(showRunnerUp({}), false);
  assert.equal(showRunnerUp({ disagreement: null }), false);
  assert.equal(showRunnerUp({ disagreement: "0.9" }), false);
  assert.equal(showRunnerUp({ disagreement: Number.NaN }), false);
});

// The threshold is copied from the backend, so the card and the reply text name the runner up in the same cases.
test("the threshold is the backend's RUNNER_UP_DISAGREEMENT in core/agent.py", () => {
  const match = /^RUNNER_UP_DISAGREEMENT = ([0-9.]+)$/m.exec(AGENT);
  assert.ok(match, "RUNNER_UP_DISAGREEMENT not found in core/agent.py");
  assert.equal(RUNNER_UP_DISAGREEMENT, Number(match[1]));
});

test("every trigger the backend can send has a label, and the app knows no other", () => {
  const body = AGENT.slice(AGENT.indexOf("def _escalations("), AGENT.indexOf("def _urgency_stated("));
  const backend = [...body.matchAll(/triggers\.append\("(\w+)"\)/g)].map((match) => match[1]);
  assert.ok(backend.length > 0, "no triggers found in _escalations");
  assert.deepEqual([...COUNCIL_TRIGGERS].sort(), [...backend].sort());
});

test("each trigger becomes its label key, in order, and an unknown id is left off rather than shown raw", () => {
  assert.deepEqual(triggerKeys(["above_half_per_txn_limit", "something_new", "rescue_state"]), [
    "trigger_above_half_per_txn_limit",
    "trigger_rescue_state",
  ]);
  assert.deepEqual(triggerKeys([]), []);
  assert.deepEqual(triggerKeys(null), []);
});

test("every trigger label exists in English, Portuguese and Chinese", () => {
  for (const code of ["en", "pt", "zh"]) {
    for (const key of triggerKeys(COUNCIL_TRIGGERS)) {
      assert.ok(STRINGS[code][key], `${key} missing in ${code}`);
      assert.ok(!/_/.test(STRINGS[code][key]), `${key} in ${code} reads like a raw id`);
    }
    assert.ok(STRINGS[code].council_triggers, `council_triggers missing in ${code}`);
  }
});
