import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STRINGS } from "../../src/i18n.js";

const zh = Object.values(STRINGS.zh);

// docs/decisions.md, "11 October 2026, the Chinese native speaker review", item 2: Lifeline addresses the student
// with 您, never 你, so the app's labels match the replies they sit beside.
test("no Chinese label uses 你; the app addresses the student with 您", () => {
  const informal = Object.entries(STRINGS.zh).filter(([, text]) => text.includes("你"));
  assert.deepEqual(informal.map(([key]) => key), []);
});

test("the backend's own Chinese uses 您 and never 你, which is what the app follows", () => {
  const agent = readFileSync(new URL("../../../core/agent.py", import.meta.url), "utf-8");
  assert.ok(agent.includes("您"));
  const zhTable = agent.slice(agent.indexOf('    "zh": {'), agent.indexOf("\n    },", agent.indexOf('    "zh": {')));
  assert.ok(zhTable.length > 0 && !zhTable.includes("你"));
});

// The council is 顾问团 in Lifeline's replies (core/agent.py, "council" texts), so the app says the same.
test("the council is 顾问团 everywhere in Chinese, never 委员会", () => {
  assert.equal(STRINGS.zh.council_title, "顾问团的建议");
  assert.equal(STRINGS.zh.council_triggers, "为何咨询顾问团");
  assert.deepEqual(zh.filter((text) => text.includes("委员会")), []);
  const agent = readFileSync(new URL("../../../core/agent.py", import.meta.url), "utf-8");
  assert.ok(agent.includes("顾问团选择了"), "core/agent.py no longer calls the council 顾问团");
});

// A corridor is a route to a country or region; 通道 is the app's word for a rail.
test("the first transfer on a corridor reads as the first transfer to that country or region", () => {
  assert.equal(STRINGS.zh.trigger_first_transfer_on_corridor, "首次汇往该国家或地区");
});

test("the other five trigger labels are unchanged", () => {
  assert.deepEqual(
    {
      above: STRINGS.zh.trigger_above_half_per_txn_limit,
      payee: STRINGS.zh.trigger_first_transfer_to_payee,
      cost: STRINGS.zh.trigger_cost_and_speed_differ,
      route: STRINGS.zh.trigger_route_degraded_or_down,
      rescue: STRINGS.zh.trigger_rescue_state,
    },
    {
      above: "超过单笔限额的一半",
      payee: "首次向此收款人转账",
      cost: "最便宜的路线不是最快的",
      route: "有路线不稳定或不可用",
      rescue: "卡片救援正在进行中",
    },
  );
});

// Joanne's approval on pull request 56: the corridor label on the confirmation card names the route to a country or
// region, as the corridor trigger does, and leaves 通道 to mean a rail.
test("the confirmation card's corridor label reads 汇往国家或地区, matching the corridor trigger", () => {
  assert.equal(STRINGS.zh.field_corridor, "汇往国家或地区");
  assert.ok(STRINGS.zh.trigger_first_transfer_on_corridor.includes(STRINGS.zh.field_corridor.replace("国家", "该国家")));
  assert.ok(!STRINGS.zh.field_corridor.includes("通道"));
});
