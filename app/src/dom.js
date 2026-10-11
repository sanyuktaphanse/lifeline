// Builds elements from text only. Nothing from the server is ever parsed as HTML, so a reply cannot inject markup.
import { t } from "./i18n.js";

export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;
    if (name === "class") node.className = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// A label that follows the language picker: relabel() rewrites every one of these when the language changes.
export function label(ctx, tag, key, values, attributes = {}) {
  const node = el(tag, { ...attributes, "data-i18n": key });
  if (values) node.dataset.i18nValues = JSON.stringify(values);
  node.textContent = t(ctx.lang(), key, values);
  return node;
}

export function relabel(root, code) {
  for (const node of root.querySelectorAll("[data-i18n]")) {
    const values = node.dataset.i18nValues ? JSON.parse(node.dataset.i18nValues) : undefined;
    node.textContent = t(code, node.dataset.i18n, values);
  }
  for (const node of root.querySelectorAll("[data-i18n-placeholder]")) {
    node.placeholder = t(code, node.dataset.i18nPlaceholder);
  }
}

export function errorText(ctx, error) {
  if (error && error.status === 0) return t(ctx.lang(), "network_error");
  if (error && error.status === 503) return t(ctx.lang(), "model_unavailable", { detail: detailText(error.detail) });
  return t(ctx.lang(), "server_error", { status: error?.status ?? "?", detail: detailText(error?.detail) });
}

function detailText(detail) {
  if (detail === null || detail === undefined) return "";
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}
