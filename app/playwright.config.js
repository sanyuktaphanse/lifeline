import { defineConfig, devices } from "@playwright/test";

// The app is served by serve.mjs; each test starts its own copy of the real API (tests/e2e/fixtures.js).
export default defineConfig({
  testDir: "tests/e2e",
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:3100", ...devices["Pixel 7"], browserName: "chromium" },
  webServer: { command: "node serve.mjs", env: { PORT: "3100" }, url: "http://127.0.0.1:3100", reuseExistingServer: false },
});
