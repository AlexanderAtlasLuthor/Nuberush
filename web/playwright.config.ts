// F2.27.3 — Playwright e2e harness configuration.
//
// This harness validates a deployed NubeRush *staging* stack. It is
// env-gated: `baseURL` comes from E2E_BASE_URL, and individual specs skip
// with an explicit BLOCKED reason when their required env is absent (see
// e2e/helpers.ts and docs/f2.27-smoke-checklist.md). There is intentionally
// NO `webServer` block — this harness never spins up a local dev server and
// never targets production.
//
// e2e is kept entirely separate from the Vitest unit suite: Vitest only scans
// `src/**`, while Playwright owns `./e2e`.
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  // Fail the build on accidentally committed `test.only`.
  forbidOnly: !!process.env.CI,
  retries: 0,
  // Conservative for a reachability smoke; no shared mutable state.
  fullyParallel: true,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
