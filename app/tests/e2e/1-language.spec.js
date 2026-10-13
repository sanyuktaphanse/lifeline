import { test, expect } from "./fixtures.js";

test("the picker lists exactly the languages /health sends, by their own names", async ({ page, backend, open }) => {
  const health = await (await fetch(`${backend.url}/health`)).json();
  await open();
  const options = page.locator("#lang option");
  await expect(options).toHaveText(Object.values(health.languages).map((language) => language.name));
  expect(await options.evaluateAll((nodes) => nodes.map((node) => node.value))).toEqual(Object.keys(health.languages));
});

test("choosing a language sets the page's language and direction and relabels the app", async ({ page, open }) => {
  await open();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("#tab-chat")).toHaveText("Chat");
  await page.selectOption("#lang", "zh");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("#tab-chat")).toHaveText("对话");
  await page.selectOption("#lang", "pt");
  await expect(page.locator("#tab-chat")).toHaveText("Conversa");
});

// Not the live server: /health is answered with one extra right to left language, to prove the list is never
// hardcoded and that direction is applied from /health. Every other call still goes to the real API.
test("a language added to /health appears with its direction, and English labels around it", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/health`, async (route) => {
    const real = await (await route.fetch()).json();
    real.languages.ar = { direction: "rtl", name: "العربية" };
    await route.fulfill({ json: real });
  });
  await open();
  await expect(page.locator("#lang option")).toHaveCount(4);
  await page.selectOption("#lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("#tab-chat")).toHaveText("Chat");
});

test("with the server down the app says so and offers a retry, and lists no languages", async ({ page, backend }) => {
  await backend.stop();
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#health-error")).toBeVisible();
  await expect(page.locator("#lang option")).toHaveCount(0);
  await backend.start();
  await page.locator("#health-error button").click();
  await expect(page.locator("#lang option")).toHaveCount(3);
  await expect(page.locator("#health-error")).toBeHidden();
});
