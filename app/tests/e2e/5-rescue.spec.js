import { test, expect } from "./fixtures.js";

// Every test here runs against the real API: the rescue calls no model, so it needs no key.

async function startRescue(page, open, { trigger = "lost", words = "I lost my Wise card", lang } = {}) {
  await open();
  if (lang) await page.selectOption("#lang", lang);
  await page.locator("#tab-rescue").click();
  await page.locator(`#rescue-trigger-${trigger}`).check();
  await page.locator("#rescue-words").fill(words);
  await page.locator("#rescue-start").click();
  await expect(page.locator("#rescue-thread .msg-lifeline")).toHaveCount(1);
}

const latest = (page) => page.locator("#rescue-thread .msg-lifeline").last();

// Waits for Lifeline's reply, as a student would, before the next step.
async function answer(page, text) {
  const before = await page.locator("#rescue-thread .msg-lifeline").count();
  await page.locator("#rescue-answer").fill(text);
  await page.locator("#rescue-answer-send").click();
  await expect(page.locator("#rescue-thread .msg-lifeline")).toHaveCount(before + 1);
}

test("LIVE: the whole rescue, from start to done, driven only by do_now", async ({ page, backend, open, storageCalls }) => {
  const bodies = [];
  page.on("request", (request) => { if (request.url().startsWith(`${backend.url}/rescue/`)) bodies.push([request.url().slice(backend.url.length), request.postDataJSON()]); });

  await startRescue(page, open);
  await expect(latest(page)).toContainText("What are the last four characters of your student pass number?");
  await expect(page.locator("#rescue-answer")).toBeVisible();
  await expect(page.locator("#rescue-step")).toContainText("S1");

  await answer(page, "1234");
  await expect(latest(page)).toContainText("does not match your plan");
  await expect(page.locator("#rescue-answer")).toHaveValue("");

  await answer(page, "7Q2K");
  const freeze = latest(page).locator(".confirm-card");
  await expect(freeze.locator(".confirm-warning")).toHaveText("This freezes the card. Payments on it stop.");
  await expect(freeze).toContainText("wise:card_01");
  await expect(page.locator("#rescue-answer")).toHaveCount(0);

  await freeze.locator(".confirm-button").click();
  await expect(latest(page).locator(".freeze")).toContainText("done");
  await expect(page.locator("#rescue-backup")).toContainText("revolut:card_02");
  const allowance = latest(page).locator(".confirm-card");
  await expect(allowance).toContainText("300 SGD");
  await expect(allowance).toContainText("self_sg");
  await expect(page.locator("#rescue-skip")).toBeVisible();

  await allowance.locator(".confirm-button").click();
  await expect(latest(page).locator(".receipt")).toContainText("completed");
  await expect(latest(page).locator(".reply-turn .turn-text")).toContainText("This turn:");
  await expect(page.locator("#rescue-done")).toBeVisible();
  await expect(page.locator("#rescue-skip")).toHaveCount(0);
  await expect(page.locator("#rescue-controls button")).toHaveCount(0);

  // What was sent: the student's words, the answers, then the two tokens exactly as the server gave them.
  expect(bodies.map(([path]) => path)).toEqual(["/rescue/start", "/rescue/step", "/rescue/step", "/rescue/step", "/rescue/step"]);
  expect(bodies[0][1]).toEqual({ user_id: "student_001", trigger: "card_lost", text: "I lost my Wise card", lang: "en" });
  expect(bodies[1][1]).toEqual({ user_id: "student_001", text: "1234", lang: "en" });
  expect(bodies.slice(3).every(([, body]) => body.text === "" && typeof body.confirmation_token === "string")).toBe(true);
  expect(bodies.every(([, body]) => !("pasted_text" in body))).toBe(true);
  expect(await storageCalls()).toEqual([]);
  expect(await page.locator("body").innerText()).not.toContain("7Q2K");
});

test("LIVE: continuing without money sends no token and finishes the rescue", async ({ page, backend, open }) => {
  await startRescue(page, open, { trigger: "stolen", words: "My card was stolen on the bus" });
  await answer(page, "7Q2K");
  await latest(page).locator(".confirm-button").click();
  await expect(page.locator("#rescue-skip")).toBeVisible();
  const sent = page.waitForRequest(`${backend.url}/rescue/step`);
  await page.locator("#rescue-skip").click();
  expect((await sent).postDataJSON()).toEqual({ user_id: "student_001", text: "", lang: "en" });
  await expect(page.locator("#rescue-done")).toBeVisible();
  await expect(latest(page).locator(".receipt")).toHaveCount(0);
});

test("LIVE: three wrong answers lock the rescue and the answer box goes away", async ({ page, open }) => {
  await startRescue(page, open);
  for (const wrong of ["1111", "2222", "3333"]) await answer(page, wrong);
  await expect(page.locator("#rescue-locked")).toBeVisible();
  await expect(page.locator("#rescue-answer")).toHaveCount(0);
  await expect(page.locator("#rescue-step")).toContainText("S1");
});

test("LIVE: with no primary card in the plan the student picks the card from card_names", async ({ page, backend, open }) => {
  await backend.restartEmpty("no-primary");
  await startRescue(page, open, { words: "I lost a card" });
  await answer(page, "7Q2K");
  const cards = page.locator("#rescue-cards button");
  await expect(cards).toHaveText(["Wise debit card", "Revolut card"]);
  const sent = page.waitForRequest(`${backend.url}/rescue/step`);
  await cards.nth(1).click();
  expect((await sent).postDataJSON()).toEqual({ user_id: "student_001", text: "Revolut card", lang: "en" });
  await expect(latest(page).locator(".confirm-card")).toContainText("revolut:card_02");
});

test("LIVE: a step when the server has no rescue running brings back the start screen", async ({ page, backend, open }) => {
  await startRescue(page, open);
  await expect(page.locator("#rescue-answer")).toBeVisible();
  await backend.restartEmpty();
  await answer(page, "7Q2K");
  await expect(latest(page)).toContainText("This turn:");
  await expect(page.locator("#rescue-start")).toBeVisible();
  await expect(page.locator("#rescue-answer")).toHaveCount(0);
});

test("LIVE: a freeze confirmation that is no longer on screen can be asked for again", async ({ page, open }) => {
  await startRescue(page, open);
  await answer(page, "7Q2K");
  await expect(latest(page).locator(".confirm-card")).toBeVisible();
  // Starting again while a rescue runs restarts nothing; the server gives the current do_now without a confirmation.
  await page.reload();
  await expect(page.locator("#lang option")).not.toHaveCount(0);
  await page.locator("#tab-rescue").click();
  await page.locator("#rescue-trigger-lost").check();
  await page.locator("#rescue-words").fill("I lost my Wise card");
  await page.locator("#rescue-start").click();
  await expect(page.locator("#rescue-reoffer")).toBeVisible();
  await page.locator("#rescue-reoffer").click();
  await expect(latest(page).locator(".confirm-card")).toContainText("wise:card_01");
});

test("pasting or dropping into the rescue is refused, so only typed words are sent", async ({ page, open }) => {
  await open();
  await page.locator("#tab-rescue").click();
  for (const name of ["paste", "drop"]) {
    await page.locator("#rescue-words").evaluate((node, kind) => {
      const data = new DataTransfer();
      data.setData("text/plain", "pasted scam text");
      const event = kind === "paste"
        ? new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true })
        : new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true });
      node.dispatchEvent(event);
    }, name);
  }
  await expect(page.locator("#rescue-words")).toHaveValue("");
  await expect(page.locator("#rescue-note")).toContainText("Pasting is off here");
});

test("LIVE: the rescue in Chinese", async ({ page, backend, open }) => {
  await startRescue(page, open, { lang: "zh", words: "我的卡丢了" });
  await expect(page.locator("#rescue-answer-send")).toHaveText("发送答案");
  await expect(latest(page).locator(".reply-turn .turn-text")).toHaveText(/^本轮：/);
  const sent = page.waitForRequest(`${backend.url}/rescue/step`);
  await answer(page, "7Q2K");
  expect((await sent).postDataJSON().lang).toBe("zh");
  await expect(latest(page).locator(".confirm-warning")).toHaveText("这会冻结这张卡，卡上的付款会停止。");
});
