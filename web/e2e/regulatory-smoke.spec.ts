// F2.27.3 — Regulatory smoke: admin regulatory page renders and the seeded
// decision-trail audit chain is visible. Advisory-only: this asserts
// visibility of the F2.27.2 fixture; it does not exercise any hold/ban/block
// behavior. Requires E2E_BASE_URL + admin credentials.
import { test, expect } from "@playwright/test";
import { adminGate, adminCreds, blockedReason, uiLogin } from "./helpers";

test.describe("admin regulatory smoke", () => {
  test("regulatory page and seeded decision trail are visible", async ({
    page,
  }) => {
    const missing = adminGate();
    test.skip(missing.length > 0, blockedReason(missing));

    const creds = adminCreds();
    if (!creds) throw new Error("admin credentials unexpectedly missing");

    await uiLogin(page, creds);

    await page.goto("/app/admin/regulatory");
    await expect(
      page.getByTestId("admin-regulatory-page"),
    ).toBeVisible();

    // F2.27.2 seed creates the regulatory fixture, so against seeded staging
    // the decision trail is a real assertion. If it is absent with env
    // present, the spec fails — it must not fake a pass.
    await expect(
      page.getByTestId("regulatory-decision-list"),
    ).toBeVisible();
  });
});
