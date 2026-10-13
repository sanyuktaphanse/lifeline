import { test, expect } from "./fixtures.js";
import { STRINGS } from "../../src/i18n.js";
import { GUIDE_SECTIONS, PROTECT_SECTIONS } from "../../src/guide-content.js";

test("the welcome shows its three cards first, and Continue opens Chat", async ({ page, backend }) => {
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#view-welcome")).toBeVisible();
  await expect(page.locator(".tabs")).toBeHidden();
  await expect(page.locator("#view-welcome .welcome-logo svg")).toBeVisible();
  const cards = page.locator(".welcome-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toBeInViewport();
  for (const index of [1, 2]) {
    await page.locator("#welcome-next").click();
    await expect(cards.nth(index)).toBeInViewport();
  }
  await expect(page.locator("#welcome-demo-note")).toContainText("sign in is not built");
  await expect(page.locator("#view-welcome input")).toHaveCount(0);
  await page.locator("#welcome-continue").click();
  await expect(page.locator("#view-welcome")).toBeHidden();
  await expect(page.locator(".tabs")).toBeVisible();
  await expect(page.locator("#tab-chat")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#view-chat")).toBeVisible();
  await page.locator("#open-welcome").click();
  await expect(page.locator("#view-welcome")).toBeVisible();
  await expect(page.locator("#view-chat")).toBeHidden();
});

test("the top bar shows the logo with the wordmark", async ({ page, open }) => {
  await open();
  await expect(page.locator(".topbar .brand svg")).toBeVisible();
  await expect(page.locator(".topbar .brand")).toHaveText("Lifeline");
});

test("the Guide shows every heading in each language", async ({ page, open }) => {
  await open();
  await page.locator("#tab-guide").click();
  for (const lang of ["en", "pt", "zh"]) {
    await page.selectOption("#lang", lang);
    const expected = [...GUIDE_SECTIONS.map((s) => s.title), "guide_protect_title", ...PROTECT_SECTIONS.map((s) => s.title)].map((key) => STRINGS[lang][key]);
    await expect(page.locator("#view-guide h2, #view-guide h3")).toHaveText(expected);
  }
});

test("tapping an example puts its words in the message box and nothing in the paste box", async ({ page, open }) => {
  await open();
  await page.locator("#tab-guide").click();
  await page.locator('#view-guide .example[data-i18n="guide_ex_rent"]').click();
  await expect(page.locator("#tab-chat")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#chat-text")).toHaveValue(STRINGS.en.guide_ex_rent);
  await expect(page.locator("#chat-paste")).toHaveValue("");
});

test("LIVE: the Guide reads verify once when shown and says development keys are signing", async ({ page, backend, open }) => {
  const calls = [];
  page.on("request", (request) => {
    if (request.url().startsWith(`${backend.url}/ledger/`)) calls.push(new URL(request.url()).pathname);
  });
  await open();
  await page.locator("#tab-guide").click();
  await expect(page.locator('#guide-verify [data-part="dev"]')).toContainText("LIFELINE_ANCHOR_SECRET");
  expect(calls).toEqual(["/ledger/student_001/verify"]);
});
