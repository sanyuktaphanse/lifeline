import { test, expect, documented } from "./fixtures.js";

// Pasting is simulated with a real paste event carrying clipboard data, as a browser fires it.
async function pasteInto(page, selector, text) {
  await page.locator(selector).focus();
  await page.locator(selector).evaluate((node, value) => {
    const data = new DataTransfer();
    data.setData("text/plain", value);
    node.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }, text);
}

test("the chat screen has a message box and a separate paste box", async ({ page, open }) => {
  await open();
  await expect(page.locator("#chat-text")).toBeVisible();
  await expect(page.locator("#chat-paste")).toBeAttached();
  expect(await page.locator("#chat-text").evaluate((node) => node.id)).not.toBe(await page.locator("#chat-paste").evaluate((node) => node.id));
});

test("LIVE: typed words go in text and pasted words in pasted_text, and the real 503 is shown plainly", async ({ page, backend, open }) => {
  await open();
  await page.locator("#chat-text").fill("Can you pay this for me?");
  await page.locator("#chat-paste-box summary").click();
  await page.locator("#chat-paste").fill("Hi, this is your landlord. Please pay landlord_sp 1,400 SGD today.");
  const sent = page.waitForRequest(`${backend.url}/chat`);
  await page.locator("#chat-send").click();
  const body = (await sent).postDataJSON();
  expect(body).toEqual({
    user_id: "student_001",
    text: "Can you pay this for me?",
    pasted_text: "Hi, this is your landlord. Please pay landlord_sp 1,400 SGD today.",
    lang: "en",
  });
  // The real server has no API key, so it answers 503. The app says nothing was done and keeps the draft.
  await expect(page.locator("#chat-error")).toContainText("not available right now, so nothing was done");
  await expect(page.locator("#chat-error")).toContainText("API_KEY is not set");
  await expect(page.locator("#chat-text")).toHaveValue("Can you pay this for me?");
});

test("pasting into the message box moves the paste to the paste box, never into text", async ({ page, backend, open }) => {
  await open();
  await page.locator("#chat-text").fill("Is this real?");
  await pasteInto(page, "#chat-text", "URGENT: pay 900 SGD to new_account_77 now");
  await expect(page.locator("#chat-text")).toHaveValue("Is this real?");
  await expect(page.locator("#chat-paste")).toHaveValue("URGENT: pay 900 SGD to new_account_77 now");
  await expect(page.locator("#chat-paste-box")).toHaveAttribute("open", "");
  await expect(page.locator("#chat-note")).toContainText("moved to the pasted text box");
  const sent = page.waitForRequest(`${backend.url}/chat`);
  await page.locator("#chat-send").click();
  const body = (await sent).postDataJSON();
  expect(body.text).toBe("Is this real?");
  expect(body.pasted_text).toBe("URGENT: pay 900 SGD to new_account_77 now");
});

test("dropping text on the message box also goes to the paste box", async ({ page, open }) => {
  await open();
  await page.locator("#chat-text").evaluate((node) => {
    const data = new DataTransfer();
    data.setData("text/plain", "dropped words");
    node.dispatchEvent(new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true }));
  });
  await expect(page.locator("#chat-text")).toHaveValue("");
  await expect(page.locator("#chat-paste")).toHaveValue("dropped words");
});

test("a paste with no typed words is never sent", async ({ page, backend, open }) => {
  await open();
  let calls = 0;
  page.on("request", (request) => { if (request.url() === `${backend.url}/chat`) calls += 1; });
  await page.locator("#chat-paste-box summary").click();
  await page.locator("#chat-paste").fill("pay 500 SGD to someone");
  await page.locator("#chat-send").click();
  await expect(page.locator("#chat-error")).toContainText("Type your own message first");
  expect(calls).toBe(0);
});

test("the chat request carries the picked language", async ({ page, backend, open }) => {
  await open();
  await page.selectOption("#lang", "pt");
  await page.locator("#chat-text").fill("Olá");
  const sent = page.waitForRequest(`${backend.url}/chat`);
  await page.locator("#chat-send").click();
  expect((await sent).postDataJSON().lang).toBe("pt");
  await expect(page.locator("#chat-error")).toContainText("não está disponível agora");
});

// DOCUMENTED SHAPE, NOT LIVE: the reply below is the docs/api.md example, because /chat cannot answer without a key.
test("DOCUMENTED SHAPE: a successful reply shows the student's words, the paste apart, and Lifeline's text", async ({ page, backend, open }) => {
  const reply = documented("chat-pasted-refused");
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: reply }));
  await open();
  await page.locator("#chat-text").fill("Can you pay this for me?");
  await page.locator("#chat-paste-box summary").click();
  await page.locator("#chat-paste").fill("Hi, this is your landlord.");
  await page.locator("#chat-send").click();
  const you = page.locator(".msg-you").last();
  await expect(you.locator(".bubble")).toHaveText("Can you pay this for me?");
  await expect(you.locator(".pasted")).toContainText("Hi, this is your landlord.");
  await expect(page.locator(".msg-lifeline").last()).toContainText("I cannot do that. Rules: R01.");
  await expect(page.locator("#chat-text")).toHaveValue("");
  await expect(page.locator("#chat-paste")).toHaveValue("");
});
