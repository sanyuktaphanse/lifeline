import { test, expect, documented } from "./fixtures.js";

const WAITING = documented("chat-transfer-waiting");
const TOKEN = WAITING.confirmation.confirmation_token;

// /chat cannot answer without a key, so the documented waiting transfer stands in for it. /confirm is the real server.
async function waitingTransfer(page, backend, open) {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: WAITING }));
  await open();
  await page.locator("#chat-text").fill("Send 1,200 SGD rent to landlord_sp in Brazil");
  await page.locator("#chat-send").click();
  const card = page.locator(".confirm-card").last();
  await expect(card).toBeVisible();
  return card;
}

test("DOCUMENTED SHAPE: the card shows the warning, the action and every route with the selected one marked", async ({ page, backend, open }) => {
  const card = await waitingTransfer(page, backend, open);
  await expect(card.locator(".confirm-warning")).toHaveText("A transfer cannot be undone once it is sent.");
  await expect(card.locator("dl.facts")).toContainText("1200 SGD");
  await expect(card.locator("dl.facts")).toContainText("landlord_sp");
  await expect(card.locator("dl.facts")).toContainText("SG>BR");
  await expect(card.locator(".routes li")).toHaveCount(3);
  await expect(card.locator(".routes li.selected")).toHaveCount(1);
  await expect(card.locator(".routes li.selected")).toContainText("Wise");
  await expect(card.locator(".routes li").nth(1)).toContainText("Simulated");
  await expect(card.locator(".confirm-expiry")).toContainText("Expires in");
  await page.selectOption("#lang", "zh");
  await expect(card.locator(".confirm-warning")).toHaveText("转账一旦发出就无法撤回。");
});

test("LIVE /confirm: the token goes back unchanged and the real 'nothing was sent' reply is shown, not an error", async ({ page, backend, open, storageCalls }) => {
  const card = await waitingTransfer(page, backend, open);
  const sent = page.waitForRequest(`${backend.url}/confirm`);
  await card.locator(".confirm-button").click();
  const request = await sent;
  expect(request.postDataJSON()).toEqual({ user_id: "student_001", confirmation_token: TOKEN, lang: "en" });
  // This token was never issued by this server, the same answer as an expired one: a 200 that says nothing was sent.
  const answer = page.locator(".msg-lifeline").last();
  await expect(answer).toContainText("That confirmation was not found, so nothing was sent.");
  await expect(page.locator("#chat-error")).toBeEmpty();
  await expect(card.locator(".confirm-button")).toBeDisabled();
  expect(await storageCalls()).toEqual([]);
  expect(await page.content()).not.toContain(TOKEN);
});

test("LIVE /confirm: two quick taps send one confirmation", async ({ page, backend, open }) => {
  const card = await waitingTransfer(page, backend, open);
  let calls = 0;
  page.on("request", (request) => { if (request.url() === `${backend.url}/confirm`) calls += 1; });
  await card.locator(".confirm-button").dblclick();
  await expect(page.locator(".msg-lifeline").last()).toContainText("nothing was sent");
  expect(calls).toBe(1);
});

test("LIVE /confirm in Chinese: the reply comes back in the picked language", async ({ page, backend, open }) => {
  const card = await waitingTransfer(page, backend, open);
  await page.selectOption("#lang", "zh");
  const sent = page.waitForRequest(`${backend.url}/confirm`);
  await card.locator(".confirm-button").click();
  expect((await sent).postDataJSON().lang).toBe("zh");
  await expect(page.locator(".msg-lifeline").last()).toContainText("本轮");
});

test("DOCUMENTED SHAPE: a reused token is a normal refusal under R10, shown as a reply", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/confirm`, (route) => route.fulfill({ json: documented("confirm-replayed") }));
  const card = await waitingTransfer(page, backend, open);
  await card.locator(".confirm-button").click();
  await expect(page.locator(".msg-lifeline").last()).toContainText("Rules: R10");
  await expect(page.locator("#chat-error")).toBeEmpty();
});

test("DOCUMENTED SHAPE: a paid transfer shows its receipt", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/confirm`, (route) => route.fulfill({ json: documented("confirm-paid") }));
  const card = await waitingTransfer(page, backend, open);
  await card.locator(".confirm-button").click();
  const receipt = page.locator(".msg-lifeline").last().locator(".receipt");
  await expect(receipt).toContainText("wise-0001");
  await expect(receipt).toContainText("completed");
});

test("DOCUMENTED SHAPE: a failed rail offers the next route under the same token, which is sent back unchanged", async ({ page, backend, open }) => {
  const retry = documented("confirm-rail-failed-retry");
  const bodies = [];
  await page.route(`${backend.url}/confirm`, async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.fulfill({ json: bodies.length === 1 ? retry : documented("confirm-paid") });
  });
  await waitingTransfer(page, backend, open);
  await page.locator(".confirm-card").last().locator(".confirm-button").click();
  const offer = page.locator(".confirm-card").last();
  await expect(offer.locator(".routes li.selected")).toContainText("Bank transfer");
  await offer.locator(".confirm-button").click();
  await expect(page.locator(".msg-lifeline").last().locator(".receipt")).toContainText("wise-0001");
  expect(bodies.map((body) => body.confirmation_token)).toEqual([TOKEN, retry.confirmation.confirmation_token]);
});

test("after the time runs out the card says it has probably expired, and still lets the server decide", async ({ page, backend, open }) => {
  await page.clock.install();
  const card = await waitingTransfer(page, backend, open);
  await page.clock.fastForward(301_000);
  await expect(card.locator(".confirm-expiry")).toContainText("probably expired");
  await expect(card.locator(".confirm-button")).toBeEnabled();
});

test("DOCUMENTED SHAPE: in Chinese the card labels the corridor 汇往国家或地区, not 通道", async ({ page, backend, open }) => {
  const card = await waitingTransfer(page, backend, open);
  await page.selectOption("#lang", "zh");
  const facts = card.locator("dl.facts");
  await expect(facts.locator("dt", { hasText: "汇往国家或地区" })).toHaveCount(1);
  await expect(facts.locator("dt", { hasText: "汇往国家或地区" }).locator("xpath=following-sibling::dd[1]")).toHaveText("SG>BR");
  await expect(facts.locator("dt", { hasText: "通道" })).toHaveCount(0);
});
