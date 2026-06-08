// F2.27.3 — Admin smoke: UI login → admin dashboard renders with its KPI grid.
// Requires E2E_BASE_URL + admin credentials (E2E_ADMIN_* or E2E_USER_*).
import { test, expect } from "@playwright/test";
import { adminGate, adminCreds, blockedReason, uiLogin } from "./helpers";

test.describe("admin dashboard smoke", () => {
  test("admin can sign in and the dashboard + KPI grid render", async ({
    page,
  }) => {
    const missing = adminGate();
    test.skip(missing.length > 0, blockedReason(missing));

    const creds = adminCreds();
    // adminGate() already guaranteed creds are present; assert for the type.
    if (!creds) throw new Error("admin credentials unexpectedly missing");

    await uiLogin(page, creds);

    // Real assertion: with env present and seeded staging, login must land on
    // the admin dashboard. If it does not, this fails — no fake pass.
    await page.goto("/app/admin");
    await expect(
      page.getByTestId("admin-dashboard-page"),
    ).toBeVisible();
    await expect(
      page.getByTestId("admin-dashboard-kpi-grid"),
    ).toBeVisible();
  });
});
