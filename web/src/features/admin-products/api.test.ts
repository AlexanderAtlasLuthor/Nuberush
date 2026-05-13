// F2.20.3: API-layer unit tests for admin-products.
//
// Strategy: stub `@/api` so every call to the admin-products API
// resolves against a controlled `apiRequest` mock. We assert URL,
// HTTP method, query string and AbortSignal forwarding — exactly what
// the wire contract guarantees. No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { getAdminProducts } from "./api";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue({
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
  });
});

describe("getAdminProducts", () => {
  it("calls GET /admin/products with no query string when no filters provided", async () => {
    await getAdminProducts();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products");
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset", async () => {
    await getAdminProducts({ limit: 25, offset: 50 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?limit=25&offset=50");
  });

  it("preserves offset=0 explicitly (does not drop the falsy value)", async () => {
    await getAdminProducts({ offset: 0 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?offset=0");
  });

  it("preserves limit=0 so the backend can return 422", async () => {
    await getAdminProducts({ limit: 0 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?limit=0");
  });

  it("trims q before forwarding", async () => {
    await getAdminProducts({ q: "  milk  " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?q=milk");
  });

  it("drops an empty q string entirely", async () => {
    await getAdminProducts({ q: "" });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products");
    expect(path).not.toMatch(/q=/);
  });

  it("drops a whitespace-only q string entirely", async () => {
    await getAdminProducts({ q: "   " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products");
    expect(path).not.toMatch(/q=/);
  });

  it("trims category before forwarding", async () => {
    await getAdminProducts({ category: "  dairy  " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?category=dairy");
  });

  it("drops an empty category string entirely", async () => {
    await getAdminProducts({ category: "" });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products");
    expect(path).not.toMatch(/category=/);
  });

  it("drops a whitespace-only category string entirely", async () => {
    await getAdminProducts({ category: "   " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products");
    expect(path).not.toMatch(/category=/);
  });

  it("preserves allowed_for_sale=false (does not drop the falsy boolean)", async () => {
    await getAdminProducts({ allowed_for_sale: false });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?allowed_for_sale=false");
  });

  it("preserves is_active=false (does not drop the falsy boolean)", async () => {
    await getAdminProducts({ is_active: false });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?is_active=false");
  });

  it("serialises compliance_status as the enum literal", async () => {
    await getAdminProducts({ compliance_status: "restricted" });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?compliance_status=restricted");
  });

  it("omits filters that are undefined", async () => {
    await getAdminProducts({
      limit: 10,
      offset: undefined,
      q: undefined,
      compliance_status: undefined,
      allowed_for_sale: undefined,
      is_active: undefined,
      category: undefined,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?limit=10");
  });

  it("combines all filters correctly in a single query string", async () => {
    await getAdminProducts({
      limit: 0,
      offset: 0,
      q: "  milk  ",
      category: "  dairy  ",
      allowed_for_sale: false,
      is_active: false,
      compliance_status: "restricted",
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    // URLSearchParams emits in insertion order. We control that order
    // in api.ts (limit, offset, q, compliance_status, allowed_for_sale,
    // is_active, category).
    expect(path).toBe(
      "/admin/products?" +
        "limit=0" +
        "&offset=0" +
        "&q=milk" +
        "&compliance_status=restricted" +
        "&allowed_for_sale=false" +
        "&is_active=false" +
        "&category=dairy",
    );
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminProducts({ limit: 10 }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("never serialises store_id as a query param", async () => {
    // TypeScript already prevents `store_id` from existing on
    // AdminProductsFilters; this test pins the runtime guarantee for
    // future callers that might bypass the type (e.g. raw input forms
    // or a loose `any`-typed spread).
    await getAdminProducts({
      // @ts-expect-error — store_id is intentionally not part of the
      // AdminProductsFilters contract (F2.20.0 §4). The cast pins the
      // runtime behavior even when the type guard is bypassed.
      store_id: "10a233d4-63a7-41f3-aecb-41dfb8f58737",
      limit: 10,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/products?limit=10");
    expect(path).not.toMatch(/store_id/);
  });
});
