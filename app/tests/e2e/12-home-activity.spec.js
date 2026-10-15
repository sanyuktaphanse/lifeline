import { test, expect, documented } from "./fixtures.js";
import { STRINGS } from "../../src/i18n.js";

const WAITING = documented("chat-transfer-waiting");

// The example of docs/api.md, GET /reminders/{user_id}, copied word for word.
const REMINDERS = {
  user_id: "student_001",
  now: "2026-10-09T00:00:00Z",
  due: [{ text: "Rent is due on 1 October", due: "2026-09-28T00:00:00Z", seq: 15 }],
  upcoming: [{ text: "Renew the student pass", due: "2026-11-02T00:00:00Z", seq: 20 }],
};

function recordCalls(page, backend) {
  const calls = [];
  page.on("request", (request) => {
    if (request.url().startsWith(backend.url)) calls.push({ method: request.method(), path: new URL(request.url()).pathname, body: request.postData() ?? "" });
  });
  return calls;
}

async function toHome(page, backend, trip) {
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#lang option")).not.toHaveCount(0);
  await page.locator("#welcome-continue").click();
  if (trip) {
    await page.selectOption("#onb-home", trip.home);
    await page.selectOption("#onb-study", trip.study);
    await page.locator('input[name="onb-purpose"][value="exchange"]').check();
    await page.locator("#onb-continue").click();
  }
  await page.locator("#onb-skip").click();
  await expect(page.locator("#view-home")).toBeVisible();
}

// The real server freezes a card and pays the allowance, so the ledger holds a rescue, a freeze and a payment.
async function rescueWithMoney(backend) {
  const post = async (path, body) => (await fetch(`${backend.url}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
  await post("/rescue/start", { user_id: "student_001", trigger: "card_lost", text: "I lost my Wise card" });
  const freeze = await post("/rescue/step", { user_id: "student_001", text: "7Q2K" });
  const money = await post("/rescue/step", { user_id: "student_001", confirmation_token: freeze.confirmation.confirmation_token });
  await post("/rescue/step", { user_id: "student_001", confirmation_token: money.confirmation.confirmation_token });
}

test("LIVE: Home greets the place of study, has no balance, and reads the reminders under the bell", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await toHome(page, backend, { home: "IN", study: "SG" });
  await expect(page.locator("#tab-home")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#home-greeting")).toHaveText("Hello. Lifeline is ready for your time in Singapore.");
  await expect(page.locator("#view-home")).not.toContainText(/balance/i);
  await expect(page.locator("#home-reminders")).toBeHidden();
  await page.locator("#home-bell").click();
  await expect(page.locator("#home-bell")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#home-reminders")).toContainText("Nothing coming up.");
  expect(calls.filter((call) => call.path === "/reminders/student_001").map((call) => call.method)).toEqual(["GET"]);
});

test("DOCUMENTED SHAPE: due reminders are counted on the bell and listed first", async ({ page, backend }) => {
  await page.route(`${backend.url}/reminders/student_001`, (route) => route.fulfill({ json: REMINDERS }));
  await toHome(page, backend);
  await expect(page.locator("#home-bell .count")).toHaveText("1");
  await page.locator("#home-bell").click();
  const items = page.locator("#home-reminders li");
  await expect(items).toHaveCount(2);
  await expect(items.nth(0)).toContainText("Rent is due on 1 October");
  await expect(items.nth(0).locator(".badge")).toHaveText("Due");
  await expect(items.nth(1)).toContainText("Renew the student pass");
  await expect(items.nth(1).locator(".badge")).toHaveCount(0);
});

test("DOCUMENTED SHAPE: a Home card sends its words at once, in text and never in pasted_text", async ({ page, backend }) => {
  const bodies = [];
  await page.route(`${backend.url}/chat`, async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.fulfill({ json: WAITING });
  });
  await toHome(page, backend, { home: "CN", study: "SG" });
  const home = page.locator('.home-card[data-card="home"]');
  await expect(home).toContainText("Money from China");
  await expect(home).toContainText("Sends: My family wants to send money from China. What will the bank ask for?");
  await page.locator('.home-card[data-card="rent"]').click();
  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator(".confirm-card")).toBeVisible();
  expect(bodies).toEqual([{ user_id: "student_001", text: STRINGS.en.guide_ex_rent, lang: "en" }]);
});

test("the Lost card on Home opens the Lost card tab and sends nothing", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await toHome(page, backend);
  await page.locator('.home-card[data-card="lost"]').click();
  await expect(page.locator("#tab-rescue")).toHaveAttribute("aria-selected", "true");
  expect(calls.filter((call) => call.method === "POST")).toEqual([]);
});

test("DOCUMENTED SHAPE: an empty chat offers starters, with the home country one, and they go once a message is sent", async ({ page, backend }) => {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: WAITING }));
  await toHome(page, backend, { home: "BR", study: "SG" });
  await page.locator("#tab-chat").click();
  const starters = page.locator("#chat-starters .starter");
  await expect(starters).toHaveText([STRINGS.en.guide_ex_rent, "How can my family send me money from Brazil?", "How do I spot a scam message?"]);
  await starters.nth(2).click();
  await expect(page.locator(".msg-you .bubble")).toHaveText("How do I spot a scam message?");
  await expect(page.locator("#chat-starters")).toBeHidden();
});

test("DOCUMENTED SHAPE: routes have friendly names, the Simulated tag, a tick on the chosen one and the true sentence", async ({ page, backend, open }) => {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: WAITING }));
  await open();
  await page.locator("#chat-text").fill("Send this month's rent of 1,200 SGD to my landlord in Brazil");
  await page.locator("#chat-send").click();
  const card = page.locator(".confirm-card");
  await expect(card.locator(".routes .route-name")).toHaveText(["Wise", "Pix", "Bank transfer"]);
  await expect(card.locator('.routes li[data-rail="sim_pix"]')).toContainText("Simulated");
  await expect(card.locator(".routes .route-tick")).toHaveCount(1);
  await expect(card.locator('.routes li[data-rail="wise"] .route-tick')).toHaveText("✓");
  await expect(card.locator(".route-rule")).toHaveText("Lifeline picks the cheapest route not marked Simulated. Simulated routes follow a real rail's rules, for practice.");
});

test("DOCUMENTED SHAPE: Copy is offered only on a reply with the model's words, and copies only them", async ({ page, backend, open, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const turnOnly = { ...WAITING, text: WAITING.turn_summary, confirmation: null };
  let answer = WAITING;
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: answer }));
  await open();
  await page.locator("#chat-text").fill("Send rent");
  await page.locator("#chat-send").click();
  const first = page.locator(".msg-lifeline").first();
  await first.locator(".reply-copy").click();
  await expect(first.locator(".reply-copy")).toHaveText("Copied");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toBe(WAITING.text.slice(0, WAITING.text.indexOf(WAITING.turn_summary)).trim());
  answer = turnOnly;
  await page.locator("#chat-text").fill("And again");
  await page.locator("#chat-send").click();
  await expect(page.locator(".msg-lifeline")).toHaveCount(2);
  await expect(page.locator(".msg-lifeline").nth(1).locator(".reply-turn")).toBeVisible();
  await expect(page.locator(".msg-lifeline").nth(1).locator(".reply-copy")).toHaveCount(0);
});

test("a one tap answer fills the Lost card box, follows lost or stolen, and pasting stays off", async ({ page, open }) => {
  await open();
  await page.locator("#tab-rescue").click();
  const quick = page.locator(".quick-answer");
  await expect(quick).toHaveText(["I lost it on transport", "I left it somewhere", "I can't find it"]);
  await quick.nth(1).click();
  await expect(page.locator("#rescue-words")).toHaveValue("I left it somewhere");
  await page.locator("#rescue-trigger-stolen").check();
  await expect(quick).toHaveText(["It was taken from my bag", "My phone and card were taken"]);
  await page.locator("#rescue-words").fill("");
  await page.locator("#rescue-words").focus();
  await page.evaluate(() => {
    const data = new DataTransfer();
    data.setData("text/plain", "pasted words");
    document.getElementById("rescue-words").dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  });
  await expect(page.locator("#rescue-words")).toHaveValue("");
});

test("LIVE: one tap answer starts a real rescue with those words in text", async ({ page, backend, open }) => {
  const calls = recordCalls(page, backend);
  await open();
  await page.locator("#tab-rescue").click();
  await page.locator(".quick-answer").first().click();
  await page.locator("#rescue-start").click();
  await expect(page.locator("#rescue-answer")).toBeVisible();
  const start = calls.find((call) => call.path === "/rescue/start");
  expect(JSON.parse(start.body)).toMatchObject({ user_id: "student_001", trigger: "card_lost", text: "I lost it on transport" });
});

test("LIVE: Activity lists the rescue in plain words by day, with every entry under Advanced", async ({ page, backend, open }) => {
  await rescueWithMoney(backend);
  const entries = await (await fetch(`${backend.url}/ledger/student_001`)).json();
  await open();
  await page.locator("#tab-activity").click();
  const rows = page.locator("#activity-list .act-row");
  await expect(rows).toHaveText([/Ana was told by WhatsApp/, /Replacement card steps given/, /Sent 300 SGD to your own Singapore account/, /Card frozen/, /Lost card rescue started/]);
  await expect(page.locator("#activity-list .day h3")).toHaveText(["Today"]);
  await expect(rows.first()).toContainText(`Ledger entry #${entries.findLast((entry) => entry.payload?.kind === "family_notice").seq}`);
  await expect(page.locator("#activity-advanced")).not.toHaveAttribute("open", "");
  await page.locator("#activity-advanced summary").click();
  await expect(page.locator("#ledger-entries > li")).toHaveCount(entries.length);
  await page.selectOption("#lang", "zh");
  await expect(page.locator("#activity-list .day h3")).toHaveText(["今天"]);
  await expect(rows.nth(3)).toContainText("卡已冻结");
});

test("LIVE: an empty Activity says so", async ({ page, open }) => {
  await open();
  await page.locator("#tab-activity").click();
  await expect(page.locator("#activity-list")).toContainText("Nothing here yet.");
});
