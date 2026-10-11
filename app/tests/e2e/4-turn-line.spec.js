import { test, expect, documented } from "./fixtures.js";

async function confirmNeverIssued(page, backend, open, lang) {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: documented("chat-transfer-waiting") }));
  await open();
  if (lang) await page.selectOption("#lang", lang);
  await page.locator("#chat-text").fill("Send 1,200 SGD rent to landlord_sp in Brazil");
  await page.locator("#chat-send").click();
  await page.locator(".confirm-button").last().click();
  await expect(page.locator(".msg-lifeline")).toHaveCount(2);
  return page.locator(".msg-lifeline").last();
}

test("LIVE: the real /confirm reply shows 'This turn:' as its own last line, apart from the rest", async ({ page, backend, open }) => {
  const reply = await confirmNeverIssued(page, backend, open);
  await expect(reply.locator(".reply-body")).toHaveText("That confirmation was not found, so nothing was sent.");
  await expect(reply.locator(".reply-turn .turn-text")).toHaveText("This turn: a confirmation: not accepted, so nothing was done.");
  await expect(reply.locator(".reply-turn .turn-label")).toHaveText("What this turn did");
  await expect(reply.locator(".reply-blocked")).toHaveCount(0);
  expect(await reply.locator(".reply > *").last().evaluate((node) => node.classList.contains("reply-turn"))).toBe(true);
});

test("LIVE: the turn line in Portuguese and Chinese", async ({ page, backend, open }) => {
  const zh = await confirmNeverIssued(page, backend, open, "zh");
  await expect(zh.locator(".reply-turn .turn-text")).toHaveText(/^本轮：/);
  await expect(zh.locator(".reply-turn .turn-label")).toHaveText("本轮做了什么");
  await page.selectOption("#lang", "pt");
  await page.locator("#chat-text").fill("Mande 1.200 SGD");
  await page.locator("#chat-send").click();
  await expect(page.locator(".confirm-card")).toHaveCount(2);
  await page.locator(".confirm-button").last().click();
  await expect(page.locator(".msg-lifeline")).toHaveCount(4);
  await expect(page.locator(".msg-lifeline").last().locator(".reply-turn .turn-text")).toHaveText(/^Neste turno:/);
});

test("DOCUMENTED SHAPE: a blocked paste puts its sentence at the top, the turn line at the bottom", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: documented("chat-pasted-refused") }));
  await open();
  await page.locator("#chat-text").fill("Can you pay this for me?");
  await page.locator("#chat-paste-box summary").click();
  await page.locator("#chat-paste").fill("Hi, this is your landlord.");
  await page.locator("#chat-send").click();
  const reply = page.locator(".msg-lifeline").last();
  const order = await reply.locator(".reply > *").evaluateAll((nodes) => nodes.map((node) => node.className.split(" ")[0]));
  expect(order[0]).toBe("reply-blocked");
  expect(order.at(-1)).toBe("reply-turn");
  await expect(reply.locator(".reply-blocked .blocked-text")).toHaveText(/^Text you pasted asked Lifeline to make a payment/);
  await expect(reply.locator(".reply-body")).toHaveText(/^I cannot do that\. Rules: R01\./);
  await expect(reply.locator(".reply-body")).not.toContainText("This turn:");
  await expect(reply.locator(".reply-body")).not.toContainText("Text you pasted");
  await expect(reply.locator(".reply-turn .turn-text")).toHaveText("This turn: a transfer: refused under R01.");
});
