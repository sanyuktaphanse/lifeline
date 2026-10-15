// Lifeline's mark: one continuous line with a single heartbeat pulse in the middle, drawn in the accent colour
// through currentColor, so it follows the light and dark themes. An original drawing; the favicon in index.html
// draws the same path.
const SVG = "http://www.w3.org/2000/svg";

export const LOGO_VIEWBOX = "0 0 48 24";
export const LOGO_PATH = "M2 12H15L18 7L22 19L26 3L29 15L31 12H46";

// The mark alone, `height` pixels tall. It is decoration: the wordmark or the page says Lifeline in words.
export function logoMark(height) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", LOGO_VIEWBOX);
  svg.setAttribute("width", String(height * 2));
  svg.setAttribute("height", String(height));
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.classList.add("logo-mark");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", LOGO_PATH);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", height >= 64 ? "2" : "2.6");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}

// The mark with the wordmark beside it, sized by the mark's height.
export function logo(height) {
  const wordmark = document.createElement("span");
  wordmark.className = "logo-word";
  wordmark.textContent = "Lifeline";
  const node = document.createElement("span");
  node.className = "logo";
  node.style.setProperty("--logo-size", `${height}px`);
  node.append(logoMark(height), wordmark);
  return node;
}

// The heartbeat orb: a violet sphere with the logo's pulse beating across it, as on a heart monitor. Decoration
// only, so it is hidden from screen readers; with reduced motion asked for, it holds still (styles.css).
export function orb(size = "large") {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", LOGO_VIEWBOX);
  svg.setAttribute("focusable", "false");
  for (const kind of ["trace-base", "trace"]) {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", LOGO_PATH);
    path.setAttribute("class", kind);
    path.setAttribute("pathLength", "100");
    svg.append(path);
  }
  const node = document.createElement("div");
  node.className = `orb orb-${size}`;
  node.setAttribute("aria-hidden", "true");
  node.append(svg);
  return node;
}
