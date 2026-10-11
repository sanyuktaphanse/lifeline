import { test, expect } from "./fixtures.js";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// The ledger is filled through the real rescue API: a confirmed card freeze writes entries and anchors the head.
async function freezeACard(backend) {
  const post = async (path, body) => (await fetch(`${backend.url}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
  await post("/rescue/start", { user_id: "student_001", trigger: "card_lost", text: "I lost my Wise card" });
  const offer = await post("/rescue/step", { user_id: "student_001", text: "7Q2K" });
  await post("/rescue/step", { user_id: "student_001", confirmation_token: offer.confirmation.confirmation_token });
}

async function openLedger(page, open) {
  await open();
  await page.locator("#tab-ledger").click();
  await expect(page.locator("#ledger-status [data-part]")).not.toHaveCount(0);
}

test("LIVE: an empty ledger is intact, not anchored yet, with payments allowed and development mode named", async ({ page, open }) => {
  await openLedger(page, open);
  await expect(page.locator('[data-part="chain"]')).toHaveText("Every entry is intact.");
  await expect(page.locator('[data-part="anchor"]')).toHaveText("Not anchored yet (local).");
  await expect(page.locator('[data-part="hold"]')).toHaveText("Payments may go ahead.");
  await expect(page.locator('[data-part="dev"]')).toContainText("LIFELINE_ANCHOR_SECRET");
  await expect(page.locator("#ledger-empty")).toBeVisible();
});

test("LIVE: after a card freeze the entries are listed newest first and the anchor checks", async ({ page, backend, open }) => {
  await freezeACard(backend);
  const entries = await (await fetch(`${backend.url}/ledger/student_001`)).json();
  const verify = await (await fetch(`${backend.url}/ledger/student_001/verify`)).json();
  await openLedger(page, open);
  await expect(page.locator("#ledger-entries > li")).toHaveCount(entries.length);
  await expect(page.locator("#ledger-entries > li").first()).toHaveAttribute("data-seq", String(entries.at(-1).seq));
  await expect(page.locator("#ledger-entries")).toContainText("anchor");
  await expect(page.locator('[data-part="anchor"]').first()).toContainText(`Entry ${verify.anchor.head_seq} is anchored (local) and the anchor checks.`);
  await expect(page.locator('[data-part="chain"]')).toHaveText("Every entry is intact.");
  await page.selectOption("#lang", "pt");
  await expect(page.locator('[data-part="chain"]')).toHaveText("Todos os registros estão íntegros.");
});

test("LIVE: a ledger edited on disk shows the first broken entry and the integrity hold after a restart", async ({ page, backend, open }) => {
  await freezeACard(backend);
  await backend.stop();
  const file = join(backend.data, "ledger.jsonl");
  const lines = readFileSync(file, "utf-8").split("\n");
  const first = JSON.parse(lines[0]);
  first.payload.turn = 99;
  lines[0] = JSON.stringify(first);
  writeFileSync(file, lines.join("\n"));
  await backend.start();
  const verify = await (await fetch(`${backend.url}/ledger/student_001/verify`)).json();
  expect(verify.first_broken_seq).toBe(1);
  await openLedger(page, open);
  await expect(page.locator('[data-part="chain"]')).toHaveText("The ledger chain breaks at entry 1.");
  await expect(page.locator('[data-part="hold"]')).toContainText("Payments are paused:");
  await expect(page.locator('#ledger-entries > li[data-seq="1"]')).toHaveClass(/broken/);
  await expect(page.locator('#ledger-entries > li[data-seq="2"]')).not.toHaveClass(/broken/);
});

test("LIVE: refresh reads the ledger again", async ({ page, backend, open }) => {
  await openLedger(page, open);
  await expect(page.locator("#ledger-empty")).toBeVisible();
  await freezeACard(backend);
  await page.locator("#ledger-refresh").click();
  await expect(page.locator("#ledger-entries > li")).not.toHaveCount(0);
});
