import { test } from "node:test";
import assert from "node:assert/strict";
import { routeBlocked } from "../../src/routes.js";

const UP = { status: "up", limit_ok: true, blocked_reason: null };

test("a route is blocked when it has a blocked reason, its limit is not ok, or its status is down", () => {
  assert.equal(routeBlocked({ ...UP, blocked_reason: "Over the daily cap." }), true);
  assert.equal(routeBlocked({ ...UP, limit_ok: false }), true);
  assert.equal(routeBlocked({ ...UP, status: "down" }), true);
});

test("a degraded route is still offered by the loop, so it is not blocked", () => {
  assert.equal(routeBlocked({ ...UP, status: "degraded" }), false);
});

test("an up route and a simulated status are not blocked", () => {
  assert.equal(routeBlocked(UP), false);
  assert.equal(routeBlocked({ ...UP, status: "simulated" }), false);
});

test("an empty blocked reason does not block", () => {
  assert.equal(routeBlocked({ ...UP, blocked_reason: "" }), false);
});
