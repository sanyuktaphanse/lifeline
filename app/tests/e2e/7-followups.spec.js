import { test, expect, documented } from "./fixtures.js";

async function startRescue(page, open) {
  await open();
  await page.locator("#tab-rescue").click();
  await page.locator("#rescue-words").fill("I lost my Wise card");
  await page.locator("#rescue-start").click();
  const reply = page.locator("#rescue-thread .msg-lifeline").last();
  await expect(reply).toBeVisible();
  return reply;
}

test("LIVE: the real reply carries blocked and turn_summary, and the app shows the turn line from it", async ({ page, backend, open }) => {
  const answer = page.waitForResponse(`${backend.url}/rescue/start`);
  const reply = await startRescue(page, open);
  const body = await (await answer).json();
  expect(body.blocked).toEqual([]);
  expect(typeof body.turn_summary).toBe("string");
  await expect(reply.locator(".reply-turn .turn-text")).toHaveText(body.turn_summary);
  await expect(reply.locator(".reply-body")).not.toContainText(body.turn_summary);
});

// The real server's reply with only the fields changed: text still holds the original sentences, so what the
// app shows can only have come from the fields.
test("LIVE, FIELDS EDITED: the app reads the turn line and the blocked lines from the fields, not from the wording", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/rescue/start`, async (route) => {
    const real = await (await route.fetch()).json();
    real.turn_summary = "Field turn line.";
    real.blocked = ["Field blocked line."];
    await route.fulfill({ json: real });
  });
  const reply = await startRescue(page, open);
  await expect(reply.locator(".reply-turn .turn-text")).toHaveText("Field turn line.");
  await expect(reply.locator(".reply-blocked .blocked-text")).toHaveText("Field blocked line.");
  // Neither field sentence is in text, so text is shown whole rather than cut wrongly.
  await expect(reply.locator(".reply-body")).toContainText("This turn: nothing was proposed, changed or sent.");
});

test("LIVE, FIELDS REMOVED: a reply without the fields falls back to the wording match", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/rescue/start`, async (route) => {
    const real = await (await route.fetch()).json();
    delete real.turn_summary;
    delete real.blocked;
    await route.fulfill({ json: real });
  });
  const reply = await startRescue(page, open);
  await expect(reply.locator(".reply-turn .turn-text")).toHaveText("This turn: nothing was proposed, changed or sent.");
  await expect(reply.locator(".reply-body")).not.toContainText("This turn:");
});

// DOCUMENTED SHAPE, routes edited: one route per status the router can give.
test("DOCUMENTED SHAPE: only a blocked reason, a limit not ok, or a down route is marked Blocked; degraded is not", async ({ page, backend, open }) => {
  const waiting = documented("chat-transfer-waiting");
  const base = waiting.confirmation.routes[0];
  waiting.confirmation.routes = [
    { ...base, rail: "up_route", status: "up" },
    { ...base, rail: "degraded_route", status: "degraded" },
    { ...base, rail: "simulated_route", status: "simulated", simulated: true },
    { ...base, rail: "down_route", status: "down" },
    { ...base, rail: "over_limit_route", limit_ok: false },
    { ...base, rail: "reason_route", blocked_reason: "Over the provider's daily cap." },
  ];
  waiting.confirmation.selected_route = { ...base, rail: "degraded_route", status: "degraded" };
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: waiting }));
  await open();
  await page.locator("#chat-text").fill("Send 1,200 SGD rent to landlord_sp in Brazil");
  await page.locator("#chat-send").click();
  const card = page.locator(".confirm-card").last();
  await expect(card.locator(".routes li")).toHaveCount(6);
  const blocked = (rail) => card.locator(`.routes li[data-rail="${rail}"] .route-blocked`);
  for (const rail of ["up_route", "degraded_route", "simulated_route"]) await expect(blocked(rail)).toHaveCount(0);
  for (const rail of ["down_route", "over_limit_route", "reason_route"]) await expect(blocked(rail)).toHaveCount(1);
  await expect(card.locator('.routes li[data-rail="degraded_route"]')).toHaveClass(/selected/);
});
