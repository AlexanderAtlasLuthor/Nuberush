// F2.27.3 — Public reachability smoke: the /login screen renders its
// email/password/sign-in controls. No credentials needed; only E2E_BASE_URL.
import { test, expect } from "@playwright/test";
import { baseUrlGate, blockedReason } from "./helpers";

test.describe("public login reachability", () => {
  test("login screen exposes email, password and sign-in controls", async ({
    page,
  }) => {
    const missing = baseUrlGate();
    test.skip(missing.length > 0, blockedReason(missing));

    await page.goto("/login");

    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(
      page.getByRole("button", { name: /sign in/i }),
    ).toBeVisible();
  });
});
