import { test, expect } from "./fixtures.js";

const TEXT = {
  en: "Demo only. No real money moves on any route.",
  pt: "Apenas demonstração. Nenhum dinheiro real se move em nenhuma rota.",
  zh: "仅为演示。任何路线都不会转移真实资金。",
};

test("the demo banner is on every tab, in every language", async ({ page, open }) => {
  await open();
  const banner = page.locator("#demo-banner");
  for (const lang of ["en", "pt", "zh"]) {
    await page.selectOption("#lang", lang);
    for (const tab of ["home", "chat", "rescue", "activity", "guide"]) {
      await page.locator(`#tab-${tab}`).click();
      await expect(banner).toBeVisible();
      await expect(banner).toHaveText(TEXT[lang]);
      await expect(banner).toBeInViewport();
    }
  }
  await expect(page.locator("#demo-banner")).toHaveCount(1);
});

test("the banner stays on screen when a long page is scrolled", async ({ page, open }) => {
  await open();
  await page.locator("#tab-activity").click();
  await page.evaluate(() => {
    document.body.style.minHeight = "4000px";
    window.scrollTo(0, 3000);
  });
  await expect(page.locator("#demo-banner")).toBeInViewport();
});

test("the banner shows in English even when the server is down", async ({ page, backend }) => {
  await backend.stop();
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#health-error")).toBeVisible();
  await expect(page.locator("#demo-banner")).toHaveText(TEXT.en);
});
