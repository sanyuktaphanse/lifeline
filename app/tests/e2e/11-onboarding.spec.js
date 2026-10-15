import { test, expect, documented } from "./fixtures.js";

const PHONE = "+86 138 0013 8000";
const EMAIL = "mei.test@example.com";
const ANSWER = "ZEBRA42";

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

test("Continue on the welcome opens the trip questions, and Skip keeps the sample plan", async ({ page, backend }) => {
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
  for (const words of ["Wise debit card", "Revolut card", "Ana, by WhatsApp", "300 SGD", "What are the last four characters of your student pass number?"]) {
    await expect(net).toContainText(words);
  }
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

test("the five steps keep the answer, the phone and the email off the server and out of storage", async ({ page, backend, storageCalls }) => {
  const calls = recordCalls(page, backend);
  await openWelcome(page, backend);
  await fillTrip(page, "CN", "SG");

  const step = page.locator("#onb-step");
  await expect(step).toHaveAttribute("data-step", "card");
  await expect(step).toContainText("Lifeline recommends none of them and is not paid by any of them.");
  await expect(page.locator("#onb-next")).toBeDisabled();
  await page.locator('input[name="onb-card"][value="dbs_posb"]').check();
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "backup");
  await expect(step).toContainText("Most students carry one");
  await page.locator('input[name="onb-backup"][value="yes"]').check();
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "question");
  await expect(step).toContainText("In this demo the live rescue asks the sample plan's question");
  await page.selectOption("#onb-question", "safety_q_school");
  await expect(page.locator("#onb-next")).toBeDisabled();
  await page.locator("#onb-answer").fill(ANSWER);
  await page.locator("#onb-next").click();
  await expect(page.locator("#onb-answer")).toHaveCount(0);

  await expect(step).toHaveAttribute("data-step", "contact");
  await page.locator("#onb-contact-name").fill("Mei");
  await page.selectOption("#onb-contact-rel", "parent");
  await page.locator("#onb-contact-phone").fill(PHONE);
  await page.locator("#onb-contact-email").fill(EMAIL);
  await page.selectOption("#onb-contact-channel", "wechat");
  await expect(step).toContainText("The phone and email stay on this page and are never sent");
  await page.locator("#onb-next").click();

  await expect(step).toHaveAttribute("data-step", "money");
  await expect(page.locator('input[name="onb-money"]')).toHaveCount(4);
  await page.locator('input[name="onb-money"][value="200"]').check();
  await page.locator("#onb-next").click();

  const summary = page.locator("#onb-summary");
  await expect(summary).toContainText("Nothing you set here was sent to Lifeline's server.");
  await expect(summary).toContainText("DBS / POSB");
  await expect(summary).toContainText("Mei, by WeChat");
  await page.locator("#onb-done").click();

  await expect(page.locator("#view-chat")).toBeVisible();
  await expect(page.locator("#chat-greeting")).toHaveText("Hello. Lifeline is ready for your time in Singapore.");
  await page.locator("#open-me").click();
  await expect(page.locator("#me-trip")).toContainText("Exchange, from China to Singapore");
  await expect(page.locator("#me-net .badge")).toHaveCount(0);
  await expect(page.locator("#me-net")).toContainText("200 SGD");
  await expect(page.locator("#me-net")).toContainText("Set. The answer is not stored.");
  await expect(page.locator("#me-net")).toContainText(`On this page only: ${PHONE}, ${EMAIL}`);

  expect(await page.content()).not.toContain(ANSWER);
  for (const call of calls) {
    expect(`${call.method} ${call.path}`).toBe("GET /health");
    for (const secret of [PHONE, EMAIL, ANSWER, "Mei"]) expect(call.body).not.toContain(secret);
  }
  expect(await storageCalls()).toEqual([]);
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
