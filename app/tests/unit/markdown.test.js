import { test } from "node:test";
import assert from "node:assert/strict";
import { parseMarkdown } from "../../src/markdown.js";

const t = (text) => ({ type: "text", text });
const strong = (...children) => ({ type: "strong", children });
const em = (...children) => ({ type: "em", children });
const p = (...lines) => ({ type: "p", lines });

test("plain text is one paragraph of one line", () => {
  assert.deepEqual(parseMarkdown("Hello there."), [p([t("Hello there.")])]);
});

test("**bold** becomes strong and *italic* becomes em", () => {
  assert.deepEqual(parseMarkdown("Send **1200 SGD** now, *not* later."), [
    p([t("Send "), strong(t("1200 SGD")), t(" now, "), em(t("not")), t(" later.")]),
  ]);
});

test("italic inside bold, and bold at the very start and end", () => {
  assert.deepEqual(parseMarkdown("**very *important***"), [p([strong(t("very "), em(t("important")))])]);
  assert.deepEqual(parseMarkdown("**A** and **B**"), [p([strong(t("A")), t(" and "), strong(t("B"))])]);
});

test("underscores are never markup, so ids like landlord_sp and pasted_text stay whole", () => {
  assert.deepEqual(parseMarkdown("Pay landlord_sp from pasted_text, __not__ _this_."), [
    p([t("Pay landlord_sp from pasted_text, __not__ _this_.")]),
  ]);
});

test("a lone or unclosed asterisk stays literal", () => {
  assert.deepEqual(parseMarkdown("5 * 3 is 15"), [p([t("5 * 3 is 15")])]);
  assert.deepEqual(parseMarkdown("**not closed"), [p([t("**not closed")])]);
  assert.deepEqual(parseMarkdown("a*b*c"), [p([t("a*b*c")])]);
  assert.deepEqual(parseMarkdown("** spaced **"), [p([t("** spaced **")])]);
});

test("a blank line starts a new paragraph and a single newline is a line break", () => {
  assert.deepEqual(parseMarkdown("One\ntwo\n\nThree"), [p([t("One")], [t("two")]), p([t("Three")])]);
});

test("lines starting with a dash, an asterisk or a plus make a bullet list", () => {
  assert.deepEqual(parseMarkdown("Routes:\n- **wise**, fee 5.60\n* sim_pix\n+ bank_wire"), [
    p([t("Routes:")]),
    { type: "ul", items: [[strong(t("wise")), t(", fee 5.60")], [t("sim_pix")], [t("bank_wire")]] },
  ]);
});

test("numbered lines make a numbered list that keeps its first number", () => {
  assert.deepEqual(parseMarkdown("1. Freeze the card\n2. Use the *backup*"), [
    { type: "ol", start: 1, items: [[t("Freeze the card")], [t("Use the "), em(t("backup"))]] },
  ]);
  assert.equal(parseMarkdown("3. Third\n4. Fourth")[0].start, 3);
  assert.equal(parseMarkdown("1) First")[0].type, "ol");
});

test("a list ends at a blank line or a line that is not an item", () => {
  assert.deepEqual(parseMarkdown("- a\n- b\nAfter"), [
    { type: "ul", items: [[t("a")], [t("b")]] },
    p([t("After")]),
  ]);
});

test("a bullet list followed by a numbered list makes two lists", () => {
  const blocks = parseMarkdown("- a\n1. b");
  assert.deepEqual(blocks.map((block) => block.type), ["ul", "ol"]);
});

test("HTML in the text is kept as plain text, never markup", () => {
  assert.deepEqual(parseMarkdown("<b>hi</b> <script>x()</script>"), [p([t("<b>hi</b> <script>x()</script>")])]);
});

test("text that is not a string gives no blocks", () => {
  assert.deepEqual(parseMarkdown(""), []);
  assert.deepEqual(parseMarkdown(null), []);
});

test("bold works next to Chinese characters with no spaces around it", () => {
  assert.deepEqual(parseMarkdown("请**确认**金额"), [p([t("请"), strong(t("确认")), t("金额")])]);
});

test("Windows line endings are read like plain newlines", () => {
  assert.deepEqual(parseMarkdown("- a\r\n- b"), [{ type: "ul", items: [[t("a")], [t("b")]] }]);
});
