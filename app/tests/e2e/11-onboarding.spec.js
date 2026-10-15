import { test, expect, documented } from "./fixtures.js";


// Records every call to the API with its body, so a test can prove what was and was not sent.
function recordCalls(page, backend) {
  const calls = [];
  page.on("request", (request) => {
    if (request.url().startsWith(backend.url)) calls.push({ method: request.method(), path: new URL(request.url()).pathname, body: request.postData() ?? "" });
  });
  return calls;
}

async function openWelcome(page, backend) {
  await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
  await expect(page.locator("#lang option")).not.toHaveCount(0);
  await page.locator("#welcome-continue").click();
}

async function fillTrip(page, home, study, purpose = "exchange") {
  await page.selectOption("#onb-home", home);
  await page.selectOption("#onb-study", study);
  await page.locator(`input[name="onb-purpose"][value="${purpose}"]`).check();
  await page.locator("#onb-continue").click();
}

const MESSAGE =
  "Please update my plan: my backup route is Bank transfer (bank_wire); no phone wallet holds my card; my cash plan is empty.";

test("LIVE: Continue on the welcome opens the trip questions, and Skip keeps the sample plan, read from the ledger", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await openWelcome(page, backend);
  await expect(page.locator("#view-onboarding")).toBeVisible();
  await expect(page.locator("#view-onboarding h2")).toHaveText("Your trip");
  await expect(page.locator("#onb-skip-note")).toHaveText("Skip keeps the demo student's sample plan.");
  await page.locator("#onb-skip").click();
  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator("#chat-greeting")).toHaveText("Hello. Lifeline is ready to help.");
  await page.locator("#open-me").click();
  await expect(page.locator("#view-me")).toBeVisible();
  await expect(page.locator("#me-trip")).toContainText("No trip set");
  const net = page.locator("#me-net");
  await expect(net.locator(".badge")).toHaveText("Sample");
  await expect(net.locator("dd")).toHaveText([
    "Wise debit card",
    "Revolut card",
    "Wise",
    "Yes",
    "A cash pickup in Singapore, knowledge entry sg_cash_pickup_001",
    "Ana, by WhatsApp",
    "300 SGD",
    "What are the last four characters of your student pass number?",
  ]);
  expect(calls.filter((call) => call.path === "/ledger/student_001").map((call) => call.method)).toEqual(["GET"]);
});

test("the four countries with rules on file come first and bold, and any other country says it has none", async ({ page, backend }) => {
  await openWelcome(page, backend);
  const first = page.locator("#onb-home optgroup").first();
  await expect(first).toHaveAttribute("label", "Rules on file");
  await expect(first.locator("option")).toHaveText([/Brazil/, /China/, /India/, /Singapore/]);
  expect(await first.locator("option").first().evaluate((node) => getComputedStyle(node).fontWeight)).toBe("700");
  await expect(page.locator("#onb-home optgroup").nth(1).locator("option[value=FR]")).toHaveCount(1);
  await expect(page.locator("#onb-continue")).toBeDisabled();
  await page.selectOption("#onb-home", "FR");
  await expect(page.locator("#onb-home-note")).toHaveText("Lifeline has no sourced rules for France yet, so it cannot check that country's rules for you.");
  await page.selectOption("#onb-home", "CN");
  await expect(page.locator("#onb-home-note")).toBeEmpty();
  await page.selectOption("#onb-study", "SG");
  await expect(page.locator("#onb-continue")).toBeDisabled();
  await page.locator('input[name="onb-purpose"][value="degree"]').check();
  await expect(page.locator("#onb-continue")).toBeEnabled();
});

test("LIVE: the four plan steps end in one message the student sends in text; nothing else leaves the page", async ({ page, backend, storageCalls }) => {
  const calls = recordCalls(page, backend);
  await openWelcome(page, backend);
  await fillTrip(page, "CN", "SG");

  const step = page.locator("#onb-step");
  await expect(page.locator("#onb-plan-intro")).toContainText("Four parts of your plan can change in chat");
  await expect(step).toHaveAttribute("data-step", "backup_card");
  await expect(step).toContainText("On file: Revolut card");
  await expect(step).toContainText("never the main card, Wise debit card");
  await expect(page.locator('input[name="onb-backup_card"]')).toHaveCount(1);
  await expect(page.locator('input[name="onb-backup_card"][value="revolut:card_02"]')).toBeChecked();
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "backup_route");
  await expect(step).toContainText("On file: Wise");
  await expect(page.locator('input[name="onb-backup_route"]')).toHaveCount(2);
  await page.locator('input[name="onb-backup_route"][value="bank_wire"]').check();
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "wallet");
  await page.locator('input[name="onb-wallet"][value="no"]').check();
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "cash_plan");
  await expect(step).toContainText("On file: A cash pickup in Singapore, knowledge entry sg_cash_pickup_001");
  await page.locator('input[name="onb-cash_plan"][value="none"]').check();
  await page.locator("#onb-next").click();

  for (const [name, words] of [
    ["contact", "On file: Ana, by WhatsApp. Lifeline holds only a name and a channel, never a phone number or an email."],
    ["money", "Changing a limit is never done in chat: it is tier 3 by design."],
    ["question", "On file: What are the last four characters of your student pass number?"],
  ]) {
    await expect(step).toHaveAttribute("data-step", name);
    await expect(step).toContainText(words);
    await expect(step).toContainText("rule R04");
    await expect(step.locator("input, select, textarea")).toHaveCount(0);
    await page.locator("#onb-next").click();
  }

  await expect(page.locator("#onb-message")).toHaveText(MESSAGE);
  await expect(page.locator("#view-onboarding input, #view-onboarding textarea")).toHaveCount(0);
  for (const call of calls) expect(["GET /health", "GET /ledger/student_001"]).toContain(`${call.method} ${call.path}`);
  for (const call of calls) expect(call.path).not.toMatch(/CN|SG|exchange/);
  expect(await storageCalls()).toEqual([]);

  await page.locator("#onb-put-in-chat").click();
  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator("#chat-text")).toHaveValue(MESSAGE);
  await expect(page.locator("#chat-paste")).toHaveValue("");
  expect(calls.filter((call) => call.method === "POST")).toEqual([]);

  await page.locator("#chat-send").click();
  // The real /chat answers 503 here, as it does without a model key in .env (tests/e2e/backend.py).
  await expect(page.locator("#chat-error")).not.toBeEmpty();
  const sent = calls.filter((call) => call.method === "POST");
  expect(sent.map((call) => [call.path, JSON.parse(call.body)])).toEqual([["/chat", { user_id: "student_001", text: MESSAGE, lang: "en" }]]);
});

test("keeping everything as it is on file leaves nothing to send", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await openWelcome(page, backend);
  await fillTrip(page, "BR", "SG");
  for (let i = 0; i < 7; i += 1) await page.locator("#onb-next").click();
  await expect(page.locator("#onb-message-none")).toHaveText("Everything is as it is on file, so there is nothing to send.");
  await expect(page.locator("#onb-put-in-chat")).toHaveCount(0);
  await page.locator("#onb-done").click();
  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator("#chat-text")).toHaveValue("");
  expect(calls.filter((call) => call.method === "POST")).toEqual([]);
});

test("SCHEMA SHAPE: a plan update the ledger executed shows on Me and as on file in the steps", async ({ page, backend }) => {
  const entries = [{ seq: 3, ts: "2026-10-15T09:00:00Z", kind: "execution", actor: "agent", hash: "h", prev_hash: "", payload: { action: { type: "update_plan" }, result: { plan_updated: { backup_route: "bank_wire", wallet_token_present: false } } } }];
  await page.route(`${backend.url}/ledger/student_001`, (route) => route.fulfill({ json: entries }));
  await openWelcome(page, backend);
  await page.locator("#onb-skip").click();
  await page.locator("#open-me").click();
  await expect(page.locator("#me-net dd").nth(2)).toHaveText("Bank transfer");
  await expect(page.locator("#me-net dd").nth(3)).toHaveText("No");
  await page.locator("#me-change-net").click();
  await page.locator("#onb-next").click();
  await expect(page.locator("#onb-step")).toContainText("On file: Bank transfer");
  await expect(page.locator('input[name="onb-backup_route"][value="bank_wire"]')).toBeChecked();
});

test("Change on Me goes back to the trip questions with the trip kept, and returns to Me", async ({ page, backend }) => {
  await openWelcome(page, backend);
  await fillTrip(page, "BR", "SG", "internship");
  await page.locator("#onb-skip").click();
  await page.locator("#open-me").click();
  await page.locator("#me-change-trip").click();
  await expect(page.locator("#onb-home")).toHaveValue("BR");
  await page.selectOption("#onb-study", "CN");
  await page.locator("#onb-continue").click();
  await expect(page.locator("#view-me")).toBeVisible();
  await expect(page.locator("#me-trip")).toContainText("Internship, from Brazil to China");
  await expect(page.locator("#me-net .badge")).toHaveText("Sample");
  await page.locator("#me-close").click();
  await expect(page.locator("#view-chat")).toBeVisible();
});

test("Me shows the true route sentence and says sign in is coming soon", async ({ page, open }) => {
  await open();
  await page.locator("#open-me").click();
  await expect(page.locator("#me-routes")).toContainText("Lifeline picks the cheapest route not marked Simulated. Simulated routes follow a real rail's rules, for practice.");
  await expect(page.locator("#me-signin")).toContainText("Coming soon");
  await expect(page.locator("#me-signin")).toContainText("Sign in is coming soon.");
  await expect(page.locator("#view-me input, #view-me button.signin")).toHaveCount(0);
  await expect(page.locator("#me-checks")).toContainText("Lifeline has no check on file for this trip yet.");
});

test("LIVE: a check on Me runs only on a tap and shows the entry ids the server names", async ({ page, backend }) => {
  const calls = recordCalls(page, backend);
  await openWelcome(page, backend);
  await fillTrip(page, "CN", "SG");
  await page.locator("#onb-skip").click();
  await page.locator("#open-me").click();
  const button = page.locator('.me-check[data-kind="remit_from_china"]');
  await expect(button).toHaveText("Check: money from China");
  expect(calls.filter((call) => call.path === "/precheck")).toEqual([]);
  await button.click();
  const result = page.locator('.me-check-result[data-kind="remit_from_china"]');
  await expect(result).toContainText("Sources: cn_boc_anxin_009, cn_fx_quota_001, cn_cdd_004");
  await expect(result).toContainText("enrollment or admission letter");
  const posted = calls.filter((call) => call.path === "/precheck");
  expect(posted.map((call) => JSON.parse(call.body))).toEqual([{ user_id: "student_001", action_kind: "remit_from_china", provider: "cn_bank_remit_sim" }]);
});

test("the onboarding follows the language picker, country names included", async ({ page, backend }) => {
  await openWelcome(page, backend);
  await page.selectOption("#lang", "zh");
  await expect(page.locator("#view-onboarding h2")).toHaveText("您的行程");
  await expect(page.locator("#onb-home optgroup").first().locator("option")).toContainText(["中国"]);
  await page.selectOption("#onb-home", "FR");
  await expect(page.locator("#onb-home-note")).toContainText("法国");
  await page.selectOption("#lang", "pt");
  await expect(page.locator("#onb-home-note")).toContainText("França");
  await expect(page.locator("#onb-home")).toHaveValue("FR");
});

test("DOCUMENTED SHAPE: a route's rule id is shown beside it, as the server sends it", async ({ page, backend, open }) => {
  const reply = documented("chat-parent-upi-waiting");
  // docs/api.md writes the selected route as "the same route as above"; here it is that route.
  reply.confirmation.selected_route = reply.confirmation.routes[0];
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: reply }));
  await open();
  await page.locator("#chat-text").fill("Send 40,000 rupees to student_001 as a gift");
  await page.locator("#chat-send").click();
  const route = page.locator('.confirm-card .routes li[data-rail="upi_paynow_sim"]');
  await expect(route.locator(".route-source")).toHaveText("Source: in_upi_paynow_purpose_001");
});
