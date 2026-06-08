// F2.27.3 — Store smoke: UI login as a store user → inventory and audit pages
// render. Smoke-level reachability only; cross-store tenancy is out of scope.
// Requires E2E_BASE_URL + store credentials (E2E_USER_*, recommended
// owner@demo-a.nuberush.dev — password supplied via env, never hardcoded).
import { test, expect } from "@playwright/test";
import { storeGate, storeCreds, blockedReason, uiLogin } from "./helpers";

test.describe("store smoke", () => {
  test("store user can sign in and reach inventory + audit", async ({
    page,
  }) => {
    const missing = storeGate();
    test.skip(missing.length > 0, blockedReason(missing));

    const creds = storeCreds();
    if (!creds) throw new Error("store credentials unexpectedly missing");

    await uiLogin(page, creds);

    await page.goto("/app/store/inventory");
    await expect(
      page.getByRole("heading", { name: /inventory/i }),
    ).toBeVisible();
    await expect(page.getByTestId("inventory-total")).toBeVisible();

    await page.goto("/app/store/audit");
    await expect(page.getByTestId("audit-page")).toBeVisible();
    await expect(page.getByTestId("audit-feed")).toBeVisible();
  });
});
