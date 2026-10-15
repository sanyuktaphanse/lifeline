import { test, expect, documented } from "./fixtures.js";

// SCHEMA SHAPE: docs/api.md has no council example, so the council block is built from CouncilAdvice in
// contracts/schemas.py (chosen, runner_up, reason, disagreement, triggers) and added to the documented waiting transfer.
const REASON = "Wise is cheaper and arrives within a day. Pix is faster but simulated.";

function withCouncil(council) {
  const reply = documented("chat-transfer-waiting");
  reply.confirmation.council = { chosen: "wise", runner_up: "sim_pix", reason: REASON, ...council };
  return reply;
}

async function cardWith(page, backend, open, advice, lang) {
  await page.route(`${backend.url}/chat`, (route) => route.fulfill({ json: withCouncil(advice) }));
  await open();
  if (lang) await page.selectOption("#lang", lang);
  await page.locator("#chat-text").fill("Send 1,200 SGD rent to landlord_sp in Brazil");
  await page.locator("#chat-send").click();
  const council = page.locator(".confirm-card .council").last();
  await expect(council).toBeVisible();
  return council;
}

for (const score of [0, 0.4]) {
  test(`SCHEMA SHAPE: at a disagreement of ${score} the runner up is not shown`, async ({ page, backend, open }) => {
    const council = await cardWith(page, backend, open, { disagreement: score, triggers: [] });
    await expect(council).toContainText("Chose: Wise");
    await expect(council.locator(".council-runner-up")).toHaveCount(0);
  });
}

test("SCHEMA SHAPE: above 0.4 the runner up is shown", async ({ page, backend, open }) => {
  const council = await cardWith(page, backend, open, { disagreement: 0.41, triggers: [] });
  await expect(council.locator(".council-runner-up")).toHaveText("Runner up: Pix");
});

test("SCHEMA SHAPE: triggers read as short labels, never raw ids, and an unknown one is left off", async ({ page, backend, open }) => {
  const council = await cardWith(page, backend, open, {
    disagreement: 0,
    triggers: ["above_half_per_txn_limit", "first_transfer_to_payee", "a_trigger_from_the_future"],
  });
  await expect(council.locator(".council-triggers li")).toHaveText([
    "More than half of the per transfer limit",
    "First transfer to this payee",
  ]);
  await expect(council).not.toContainText("_limit");
  await expect(council).not.toContainText("a_trigger_from_the_future");
});

test("SCHEMA SHAPE: with no triggers there is no trigger list", async ({ page, backend, open }) => {
  const council = await cardWith(page, backend, open, { disagreement: 0, triggers: [] });
  await expect(council.locator(".council-triggers")).toHaveCount(0);
});

test("SCHEMA SHAPE: the reasoning text is shown exactly as sent", async ({ page, backend, open }) => {
  const council = await cardWith(page, backend, open, { disagreement: 0.9, triggers: ["cost_and_speed_differ"] });
  await expect(council.locator(".council-reason")).toHaveText(REASON);
});

test("SCHEMA SHAPE: trigger labels follow the language picker", async ({ page, backend, open }) => {
  const council = await cardWith(page, backend, open, { disagreement: 0, triggers: ["rescue_state"] }, "zh");
  await expect(council.locator(".council-triggers li")).toHaveText(["卡片救援正在进行中"]);
  await page.selectOption("#lang", "pt");
  await expect(council.locator(".council-triggers li")).toHaveText(["Há um resgate de cartão em andamento"]);
});
