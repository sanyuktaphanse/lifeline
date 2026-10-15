import { test, expect } from "./fixtures.js";

async function openWelcome(page, backend) {
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#lang option")).not.toHaveCount(0);
}

test("the welcome shows the heartbeat orb, hidden from screen readers", async ({ page, backend }) => {
  await openWelcome(page, backend);
  const orb = page.locator("#view-welcome .orb");
  await expect(orb).toBeVisible();
  await expect(orb).toHaveAttribute("aria-hidden", "true");
  await expect(orb.locator("svg path")).not.toHaveCount(0);
});

test("sliding the knob to the end starts the onboarding", async ({ page, backend }) => {
  await openWelcome(page, backend);
  const knob = page.locator("#welcome-slide-knob");
  const track = page.locator("#welcome-slider");
  await knob.scrollIntoViewIfNeeded();
  const from = await knob.boundingBox();
  const box = await track.boundingBox();
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, from.y + from.height / 2, { steps: 5 });
  await page.mouse.up();
  await expect(page.locator("#view-welcome")).toBeVisible();
  // A short drag springs back; wait until the knob is home before the second drag.
  await expect.poll(async () => Math.round((await knob.boundingBox()).x)).toBe(Math.round(from.x));
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 4, from.y + from.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator("#view-onboarding")).toBeVisible();
});

test("the knob starts on Enter from the keyboard, and the plain button stays as a fallback", async ({ page, backend }) => {
  await openWelcome(page, backend);
  await expect(page.locator("#welcome-slide-knob")).toHaveAttribute("aria-label", "Start as the demo student");
  await expect(page.locator("#welcome-continue")).toBeVisible();
  await page.locator("#welcome-slide-knob").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#view-onboarding")).toBeVisible();
});

test("the light theme is cream with a violet accent, and the tabs carry line icons", async ({ page, backend }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await openWelcome(page, backend);
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(250, 247, 242)");
  await page.locator("#welcome-continue").click();
  await page.locator("#onb-skip").click();
  for (const tab of ["home", "chat", "rescue", "activity", "guide"]) await expect(page.locator(`#tab-${tab} svg`)).toHaveCount(1);
  await expect(page.locator("#tab-chat")).toHaveText("Chat");
  expect(await page.locator('.tabs [aria-selected="true"]').evaluate((node) => getComputedStyle(node).color)).toBe("rgb(91, 63, 214)");
});

test("with reduced motion the orb holds still", async ({ page, backend }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openWelcome(page, backend);
  expect(await page.locator("#view-welcome .orb").evaluate((node) => getComputedStyle(node).animationName)).toBe("none");
});

test("LIVE: every request goes to this machine, so the app loads offline and anywhere", async ({ page, backend }) => {
  const outside = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname) && url.protocol !== "data:") outside.push(request.url());
  });
  await openWelcome(page, backend);
  await page.locator("#welcome-continue").click();
  await page.locator("#onb-skip").click();
  for (const tab of ["chat", "rescue", "activity", "guide", "home"]) await page.locator(`#tab-${tab}`).click();
  await page.locator("#open-me").click();
  expect(outside).toEqual([]);
});
