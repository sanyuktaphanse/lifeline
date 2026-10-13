// Gives each test its own fresh copy of the real API and opens the app pointed at it.
import { test as base, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const APP = fileURLToPath(new URL("../..", import.meta.url));
const PYTHON = join(APP, "..", ".venv", "bin", "python");
const DATA = join(APP, ".e2e-data");
let nextPort = 8100;

async function waitForHealth(url) {
  for (let i = 0; i < 100; i += 1) {
    try {
      if ((await fetch(`${url}/health`)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`The API at ${url} did not start`);
}

class Backend {
  constructor(name) {
    if (!existsSync(PYTHON)) throw new Error(`No ${PYTHON}. Run the README's quick start in the repository folder first.`);
    this.port = nextPort++ + Number(process.env.TEST_WORKER_INDEX || 0) * 100;
    this.url = `http://127.0.0.1:${this.port}`;
    this.data = join(DATA, `${name}-${this.port}`);
    rmSync(this.data, { recursive: true, force: true });
    mkdirSync(this.data, { recursive: true });
  }

  async start(variant) {
    const args = [join(APP, "tests", "e2e", "backend.py"), String(this.port), this.data];
    if (variant) args.push(variant);
    this.process = spawn(PYTHON, args, { stdio: "inherit" });
    await waitForHealth(this.url);
  }

  async stop() {
    if (!this.process) return;
    const exited = new Promise((resolve) => this.process.once("exit", resolve));
    this.process.kill("SIGTERM");
    await exited;
    this.process = null;
  }

  // Starts again from nothing, as deleting data/ and running make dev again would.
  async restartEmpty(variant) {
    await this.stop();
    rmSync(this.data, { recursive: true, force: true });
    mkdirSync(this.data, { recursive: true });
    await this.start(variant);
  }
}

export const test = base.extend({
  backend: async ({}, use, testInfo) => {
    const backend = new Backend(testInfo.title.replace(/\W+/g, "_").slice(0, 40));
    await backend.start();
    await use(backend);
    await backend.stop();
  },
  // Records any use of browser storage, so a test can prove the app never stores anything.
  storageCalls: async ({ page }, use) => {
    await page.addInitScript(() => {
      window.__storageCalls = [];
      for (const area of ["localStorage", "sessionStorage"]) {
        const store = window[area];
        for (const method of ["setItem", "getItem"]) {
          const original = store[method].bind(store);
          store[method] = (...args) => {
            window.__storageCalls.push(`${area}.${method}`);
            return original(...args);
          };
        }
      }
      const open = indexedDB.open.bind(indexedDB);
      indexedDB.open = (...args) => {
        window.__storageCalls.push("indexedDB.open");
        return open(...args);
      };
    });
    await use(async () => page.evaluate(() => window.__storageCalls));
  },
  open: async ({ page, backend }, use) => {
    await use(async () => {
      await page.goto(`/?api=${encodeURIComponent(backend.url)}`);
      await expect(page.locator("#lang option")).not.toHaveCount(0);
    });
  },
});

export { expect };

// A reply copied word for word from docs/api.md, for the cases the live server cannot produce without a key.
export function documented(name) {
  return JSON.parse(readFileSync(join(APP, "tests", "e2e", "documented", `${name}.json`), "utf-8"));
}
