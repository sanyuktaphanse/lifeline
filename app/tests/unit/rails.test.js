import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { RAIL_KEYS, railName } from "../../src/rails.js";

const router = readFileSync(new URL("../../../rails/fake_router.py", import.meta.url), "utf-8");

test("the routes the router quotes get friendly names, and any other rail keeps its id", () => {
  assert.equal(railName("wise", "en"), "Wise");
  assert.equal(railName("sim_pix", "en"), "Pix");
  assert.equal(railName("bank_wire", "en"), "Bank transfer");
  assert.equal(railName("bank_wire", "pt"), "Transferência bancária");
  assert.equal(railName("bank_wire", "zh"), "银行转账");
  assert.equal(railName("upi_paynow_sim", "en"), "upi_paynow_sim");
});

test("every rail with a friendly name is one rails/fake_router.py quotes", () => {
  for (const rail of Object.keys(RAIL_KEYS)) assert.ok(router.includes(`"${rail}"`), rail);
});
