// Serves this folder on http://127.0.0.1:3000 (or PORT). Only files inside app/ are served, and only to this machine.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const PORT = Number(process.env.PORT || 3000);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml" };
const SERVED = ["index.html", "styles.css", "src" + sep];

createServer(async (request, response) => {
  const path = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
  const relative = normalize(path === "/" ? "index.html" : path.slice(1));
  if (!SERVED.some((allowed) => relative === allowed || relative.startsWith(allowed)) || !TYPES[extname(relative)]) {
    response.writeHead(404).end("Not found");
    return;
  }
  try {
    const body = await readFile(join(ROOT, relative));
    response.writeHead(200, { "Content-Type": TYPES[extname(relative)], "Cache-Control": "no-store" }).end(body);
  } catch {
    response.writeHead(404).end("Not found");
  }
}).listen(PORT, "127.0.0.1", () => console.log(`Lifeline app on http://127.0.0.1:${PORT}`));
