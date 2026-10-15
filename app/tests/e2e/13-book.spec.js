import { test, expect } from "./fixtures.js";

async function toHome(page, backend) {
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#lang option")).not.toHaveCount(0);
  await page.locator("#welcome-continue").click();
  await page.locator("#onb-skip").click();
  await expect(page.locator("#view-home")).toBeVisible();
}

function recordCalls(page, backend) {
  const calls = [];
  page.on("request", (request) => {
    if (request.url().startsWith(backend.url)) calls.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  return calls;
}

test("Book and pay safely opens from Home and lists the six apps by name only, with the partner note", async ({ page, backend }) => {
  await toHome(page, backend);
  await page.locator("#open-book").click();
  const view = page.locator("#view-book");
  await expect(view).toBeVisible();
  await expect(view.locator("h2").first()).toHaveText("Book and pay safely");
  await expect(view.locator(".book-group h4")).toHaveText(["Flights", "Places to stay", "Paying abroad"]);
  await expect(view.locator(".book-group li")).toHaveText(["Singapore Airlines", "Skyscanner", "Trip.com", "Trip.com", "Trivago", "HeyMax", "YouTrip"]);
  await expect(view.locator("#book-apps-note")).toHaveText("Lifeline isn't partnered with or paid by any of these apps.");
  await expect(view.locator("img, svg, a[href]")).toHaveCount(0);
  await expect(view.locator("#book-apps")).not.toContainText(/\d/);
  await page.locator("#book-close").click();
  await expect(page.locator("#view-home")).toBeVisible();
});

test("the deposit checklist ticks in page memory only and sends nothing", async ({ page, backend, storageCalls }) => {
  const calls = recordCalls(page, backend);
  await toHome(page, backend);
  const before = calls.length;
  await page.locator("#open-book").click();
  const boxes = page.locator('#book-deposit input[type="checkbox"]');
  await expect(boxes).toHaveCount(4);
  for (let i = 0; i < 4; i += 1) await boxes.nth(i).check();
  await expect(boxes.nth(3)).toBeChecked();
  expect(calls.slice(before)).toEqual([]);
  expect(await storageCalls()).toEqual([]);
});

test("Check a message opens Chat with the question typed and the paste box open, and sends nothing", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await toHome(page, backend);
  await page.locator("#open-book").click();
  await page.locator("#book-check").click();
  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator("#chat-text")).toHaveValue("Is this booking message a scam?");
  await expect(page.locator("#chat-paste-box")).toHaveAttribute("open", "");
  await expect(page.locator("#chat-paste")).toBeFocused();
  await expect(page.locator("#chat-paste")).toHaveValue("");
  expect(calls.filter((call) => call.startsWith("POST"))).toEqual([]);
});

test("the Book page follows the language picker; app names stay as they are", async ({ page, backend }) => {
  await toHome(page, backend);
  await page.locator("#open-book").click();
  await page.selectOption("#lang", "zh");
  await expect(page.locator("#view-book h2").first()).toHaveText("安全预订与付款");
  await expect(page.locator("#book-apps-note")).toHaveText("Lifeline 与这些应用均无合作，也不从中获得任何报酬。");
  await expect(page.locator(".book-group li").first()).toHaveText("Singapore Airlines");
  await page.selectOption("#lang", "pt");
  await expect(page.locator("#view-book h2").first()).toHaveText("Reserve e pague com segurança");
});
