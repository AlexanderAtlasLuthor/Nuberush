// F2.27.3 — Product image smoke: admin products list → product detail → image
// metadata panel is visible. NO real upload is performed and Supabase Storage
// is never called (that is manual/deferred — see the smoke checklist).
// Requires E2E_BASE_URL + admin credentials.
import { test, expect } from "@playwright/test";
import { adminGate, adminCreds, blockedReason, uiLogin } from "./helpers";

test.describe("product image smoke", () => {
  test("product detail exposes the image metadata panel", async ({ page }) => {
    const missing = adminGate();
    test.skip(missing.length > 0, blockedReason(missing));

    const creds = adminCreds();
    if (!creds) throw new Error("admin credentials unexpectedly missing");

    await uiLogin(page, creds);

    await page.goto("/app/admin/products");
    await expect(page.getByTestId("admin-products-page")).toBeVisible();

    // Open the first product via its stable drilldown link. Against seeded
    // staging there is at least one product; if navigation does not reach a
    // detail with the image panel, the spec fails — no fake pass.
    await page.getByTestId("admin-products-row-drilldown").first().click();

    await expect(
      page.getByTestId("admin-product-image-panel"),
    ).toBeVisible();
  });
});
