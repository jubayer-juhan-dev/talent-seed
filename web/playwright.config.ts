import { defineConfig, devices } from "@playwright/test";

/** End-to-end tests against a running viewer (they need the real database, so they don't run in CI).
 *  Run on the VM:  TALENT_SEED_KEY=$(cut -d= -f2- /etc/talent-seed-viewer.env) pnpm e2e
 *  Another server: E2E_BASE_URL=https://… TALENT_SEED_KEY=… pnpm e2e */
export default defineConfig({
  testDir: "e2e",
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: 3,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8765",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1400, height: 950 } },
      testIgnore: /phone\.spec\.ts/,
    },
    {
      name: "phone",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, colorScheme: "dark" },
      testMatch: /phone\.spec\.ts/,
    },
  ],
});
