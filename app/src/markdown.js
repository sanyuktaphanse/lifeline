// A small markdown reader for the model's words in a reply: **bold**, *italic*, bullet lists and numbered lists,
// pipe tables, paragraphs and line breaks. Nothing else is markup. It returns plain data, and renderMarkdown builds elements
// from it with text nodes only, so nothing from the server is ever read as HTML.
//
// Underscores are never markup, because Lifeline's ids are full of them: landlord_sp, pasted_text, self_sg.
// A single * may not sit between two ASCII letters or digits, so a*b*c and 2*3*4 stay as written; ** may sit
// inside a word, because a model writes Chinese such as 请**确认**金额 with no spaces around it.
import { el } from "./dom.js";

const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d{1,9})[.)]\s+(.*)$/;
const ASCII_WORD = /[A-Za-z0-9]/;
const SEPARATOR_CELL = /^:?-+:?$/;
const SPACE = /\s/;

export function parseMarkdown(text) {
  if (typeof text !== "string" || text === "") return [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let current = null;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const table = tableAt(lines, i);
    if (table) {
      blocks.push(table.block);
      current = null;
      i = table.last;
      continue;
    }
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    if (line.trim() === "") {
      current = null;
    } else if (bullet || numbered) {
      const type = bullet ? "ul" : "ol";
      if (!current || current.type !== type) {
        current = type === "ul" ? { type, items: [] } : { type, start: Number(numbered[1]), items: [] };
        blocks.push(current);
      }
      current.items.push(parseInline(bullet ? bullet[1] : numbered[2]));
    } else {
      if (!current || current.type !== "p") {
        current = { type: "p", lines: [] };
        blocks.push(current);
      }
      current.lines.push(parseInline(line.trim()));
    }
  }
  return blocks;
}

// A pipe table, as GitHub reads one: a header row and a separator row of dashes, with a colon at the left, right or
// both ends setting a column's alignment, both with the same number of cells and both containing a pipe. Body rows
// follow until a blank line or a line with no pipe; each is filled or cut to the header's width. A \| is a pipe
// inside a cell. Without the separator row nothing is a table, so a pipe in a sentence stays text.
function tableAt(lines, i) {
  const header = lines[i];
  const separator = lines[i + 1];
  if (separator === undefined || !hasPipe(header) || !hasPipe(separator)) return null;
  const head = cellsOf(header);
  const marks = cellsOf(separator);
  if (marks.length !== head.length || !marks.every((mark) => SEPARATOR_CELL.test(mark))) return null;
  const align = marks.map((mark) => {
    const left = mark.startsWith(":");
    const right = mark.endsWith(":");
    return left && right ? "center" : right ? "right" : left ? "left" : null;
  });
  const rows = [];
  let last = i + 1;
  while (last + 1 < lines.length && lines[last + 1].trim() !== "" && hasPipe(lines[last + 1])) {
    last += 1;
    const cells = cellsOf(lines[last]).slice(0, head.length);
    while (cells.length < head.length) cells.push("");
    rows.push(cells.map(parseInline));
  }
  return { block: { type: "table", align, head: head.map(parseInline), rows }, last };
}

function hasPipe(line) {
  return /(^|[^\\])\|/.test(line);
}

function cellsOf(line) {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.replace(/\\\|/g, "|").trim());
}

function parseInline(s) {
  const out = [];
  let plain = "";
  let i = 0;
  const flush = () => {
    if (plain) out.push({ type: "text", text: plain });
    plain = "";
  };
  while (i < s.length) {
    const span = s.startsWith("**", i) ? boldAt(s, i) : s[i] === "*" ? italicAt(s, i) : null;
    if (span) {
      flush();
      out.push({ type: span.type, children: parseInline(s.slice(span.from, span.to)) });
      i = span.next;
    } else {
      plain += s[i];
      i += 1;
    }
  }
  flush();
  return out;
}

// ** opens before a character that is not a space and closes after one, at the last ** of a run of asterisks.
function boldAt(s, i) {
  if (i + 2 >= s.length || SPACE.test(s[i + 2])) return null;
  for (let j = s.indexOf("**", i + 3); j !== -1; j = s.indexOf("**", j + 1)) {
    if (s[j + 2] === "*") continue;
    if (!SPACE.test(s[j - 1])) return { type: "strong", from: i + 2, to: j, next: j + 2 };
  }
  return null;
}

// * opens before a character that is not a space or a *, and not after an ASCII letter or digit; it closes at the
// next * that follows a character that is not a space and is not followed by an ASCII letter or digit.
function italicAt(s, i) {
  const next = s[i + 1];
  if (next === undefined || next === "*" || SPACE.test(next)) return null;
  if (i > 0 && ASCII_WORD.test(s[i - 1])) return null;
  for (let j = s.indexOf("*", i + 2); j !== -1; j = s.indexOf("*", j + 1)) {
    if (SPACE.test(s[j - 1]) || (j + 1 < s.length && ASCII_WORD.test(s[j + 1]))) continue;
    return { type: "em", from: i + 1, to: j, next: j + 1 };
  }
  return null;
}

function inlineNodes(parts) {
  return parts.map((part) => (part.type === "text" ? part.text : el(part.type, {}, inlineNodes(part.children))));
}

const ALIGN_CLASS = { left: "align-left", center: "align-center", right: "align-right" };

function tableNode(block) {
  const cellNode = (tag, parts, column) => el(tag, { class: ALIGN_CLASS[block.align[column]] ?? null }, inlineNodes(parts));
  return el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      {},
      el("thead", {}, el("tr", {}, block.head.map((parts, column) => cellNode("th", parts, column)))),
      el("tbody", {}, block.rows.map((row) => el("tr", {}, row.map((parts, column) => cellNode("td", parts, column))))),
    ),
  );
}

export function renderMarkdown(text) {
  return parseMarkdown(text).map((block) => {
    if (block.type === "table") return tableNode(block);
    if (block.type === "p") {
      return el("p", {}, block.lines.flatMap((line, index) => (index === 0 ? inlineNodes(line) : [el("br"), ...inlineNodes(line)])));
    }
    const items = block.items.map((item) => el("li", {}, inlineNodes(item)));
    return block.type === "ol" ? el("ol", { start: block.start === 1 ? null : block.start }, items) : el("ul", {}, items);
  });
}
