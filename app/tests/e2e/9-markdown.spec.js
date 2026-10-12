import { test, expect, documented } from "./fixtures.js";

// DOCUMENTED SHAPE, TEXT EDITED: the docs/api.md waiting transfer with markdown written into the model's words,
// as a live model writes it. The turn line is the reply's own turn_summary and stays plain.
function withModelText(modelText) {
  const reply = documented("chat-transfer-waiting");
  reply.text = `${modelText} ${reply.turn_summary}`;
  return reply;
}

async function ask(page, backend, open, reply) {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: reply }));
  await open();
  await page.locator("#chat-text").fill("Send 1,200 SGD rent to landlord_sp in Brazil");
  await page.locator("#chat-send").click();
  const answer = page.locator(".msg-lifeline").last();
  await expect(answer).toBeVisible();
  return answer;
}

test("DOCUMENTED SHAPE, TEXT EDITED: bold, italic and lists render, with no literal asterisks left", async ({ page, backend, open }) => {
  const answer = await ask(page, backend, open, withModelText(
    "Please confirm: send **1200 SGD** to landlord_sp, *not* to anyone else.\n\nYour routes:\n- **wise**, fee 5.60 SGD\n- sim_pix, fee 0 SGD\n\n1. Check the amount\n2. Tap Confirm",
  ));
  const body = answer.locator(".reply-body");
  await expect(body.locator("strong").first()).toHaveText("1200 SGD");
  await expect(body.locator("em")).toHaveText("not");
  await expect(body.locator("ul > li")).toHaveText(["wise, fee 5.60 SGD", "sim_pix, fee 0 SGD"]);
  await expect(body.locator("ul > li").first().locator("strong")).toHaveText("wise");
  await expect(body.locator("ol > li")).toHaveText(["Check the amount", "Tap Confirm"]);
  await expect(body).not.toContainText("*");
  await expect(body).toContainText("landlord_sp");
  await expect(answer.locator(".reply-turn .turn-text")).toHaveText("This turn: a transfer of 1200 SGD to landlord_sp: proposed, waiting for your confirmation.");
});

test("DOCUMENTED SHAPE, TEXT EDITED: HTML from the model is shown as text, never run", async ({ page, backend, open }) => {
  const answer = await ask(page, backend, open, withModelText('**Hi** <img src=x onerror="window.__ran=1"><b>not bold</b>'));
  const body = answer.locator(".reply-body");
  await expect(body).toContainText('<img src=x onerror="window.__ran=1"><b>not bold</b>');
  await expect(body.locator("img, b")).toHaveCount(0);
  await expect(body.locator("strong")).toHaveText("Hi");
  expect(await page.evaluate(() => window.__ran)).toBeUndefined();
});

test("LIVE: a real reply with no markdown still shows its words unchanged", async ({ page, open }) => {
  await open();
  await page.locator("#tab-rescue").click();
  await page.locator("#rescue-words").fill("I lost my Wise card");
  await page.locator("#rescue-start").click();
  const body = page.locator("#rescue-thread .reply-body").last();
  await expect(body).toHaveText("Lifeline started a rescue. First answer the question you set before you left: What are the last four characters of your student pass number?");
});
