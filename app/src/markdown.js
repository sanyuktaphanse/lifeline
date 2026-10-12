// A small markdown reader for the model's words in a reply: **bold**, *italic*, bullet lists and numbered lists,
// paragraphs and line breaks. Nothing else is markup. It returns plain data, and renderMarkdown builds elements
// from it with text nodes only, so nothing from the server is ever read as HTML.
//
// Underscores are never markup, because Lifeline's ids are full of them: landlord_sp, pasted_text, self_sg.
// A single * may not sit between two ASCII letters or digits, so a*b*c and 2*3*4 stay as written; ** may sit
// inside a word, because a model writes Chinese such as 请**确认**金额 with no spaces around it.
import { el } from "./dom.js";

const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d{1,9})[.)]\s+(.*)$/;
const ASCII_WORD = /[A-Za-z0-9]/;
const SPACE = /\s/;

export function parseMarkdown(text) {
  if (typeof text !== "string" || text === "") return [];
  const blocks = [];
  let current = null;
  for (const line of text.replace(/\r\n?/g, "\n").split("\n")) {
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

export function renderMarkdown(text) {
  return parseMarkdown(text).map((block) => {
    if (block.type === "p") {
      return el("p", {}, block.lines.flatMap((line, index) => (index === 0 ? inlineNodes(line) : [el("br"), ...inlineNodes(line)])));
    }
    const items = block.items.map((item) => el("li", {}, inlineNodes(item)));
    return block.type === "ol" ? el("ol", { start: block.start === 1 ? null : block.start }, items) : el("ul", {}, items);
  });
}
