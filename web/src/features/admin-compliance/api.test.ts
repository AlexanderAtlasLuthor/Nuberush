// F2.20.4: API-layer unit tests for admin-compliance.
//
// Strategy: stub `@/api` so every call resolves against a controlled
// `apiRequest` mock. We assert URL, HTTP method, query string and
// AbortSignal forwarding — exactly what the wire contract guarantees.
// No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  getAdminComplianceProducts,
  getAdminComplianceSummary,
} from "./api";
import type { AdminComplianceSummary } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const EMPTY_SUMMARY: AdminComplianceSummary = {
  products: {
    total: 0,
    allowed: 0,
    restricted: 0,
    banned: 0,
    blocked: 0,
    allowed_for_sale: 0,
    not_allowed_for_sale: 0,
    inactive: 0,
  },
  reviews: { recent_count: 0, recent: [] },
  queue: { total: 0, banned: 0, restricted: 0, not_allowed_for_sale: 0 },
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(EMPTY_SUMMARY);
});

// --------------------------------------------------------------------- //
// getAdminComplianceSummary
// --------------------------------------------------------------------- //

describe("getAdminComplianceSummary", () => {
  it("calls GET /admin/compliance with no query string", async () => {
    await getAdminComplianceSummary();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance");
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminComplianceSummary(controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("does not synthesize KPI values — returns whatever apiRequest resolves to", async () => {
    const seeded: AdminComplianceSummary = {
      products: {
        total: 7,
        allowed: 4,
        restricted: 2,
        banned: 1,
        blocked: 3,
        allowed_for_sale: 5,
        not_allowed_for_sale: 2,
        inactive: 1,
      },
      reviews: { recent_count: 0, recent: [] },
      queue: { total: 3, banned: 1, restricted: 2, not_allowed_for_sale: 2 },
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(seeded);

    const result = await getAdminComplianceSummary();
    expect(result).toBe(seeded);
  });

  it("never appends a query string even on retry", async () => {
    await getAdminComplianceSummary();
    await getAdminComplianceSummary();

    for (const call of vi.mocked(apiRequest).mock.calls) {
      expect(call[0]).toBe("/admin/compliance");
      expect(call[0]).not.toMatch(/\?/);
    }
  });
});

// --------------------------------------------------------------------- //
// getAdminComplianceProducts
// --------------------------------------------------------------------- //

const EMPTY_PRODUCTS = { items: [], total: 0, limit: 50, offset: 0 };

describe("getAdminComplianceProducts", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockResolvedValue(EMPTY_PRODUCTS);
  });

  it("calls GET /admin/compliance/products with no query when no filters provided", async () => {
    await getAdminComplianceProducts();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products");
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset", async () => {
    await getAdminComplianceProducts({ limit: 25, offset: 50 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?limit=25&offset=50");
  });

  it("preserves offset=0 explicitly", async () => {
    await getAdminComplianceProducts({ offset: 0 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?offset=0");
  });

  it("preserves limit=0 so the backend can return 422", async () => {
    await getAdminComplianceProducts({ limit: 0 });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?limit=0");
  });

  it("trims q before forwarding", async () => {
    await getAdminComplianceProducts({ q: "  milk  " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?q=milk");
  });

  it("drops an empty q string entirely", async () => {
    await getAdminComplianceProducts({ q: "" });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products");
    expect(path).not.toMatch(/q=/);
  });

  it("drops a whitespace-only q string entirely", async () => {
    await getAdminComplianceProducts({ q: "   " });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products");
    expect(path).not.toMatch(/q=/);
  });

  it("preserves allowed_for_sale=false (does not drop the falsy boolean)", async () => {
    await getAdminComplianceProducts({ allowed_for_sale: false });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      "/admin/compliance/products?allowed_for_sale=false",
    );
  });

  it("preserves is_active=false (does not drop the falsy boolean)", async () => {
    await getAdminComplianceProducts({ is_active: false });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?is_active=false");
  });

  it("serialises compliance_status as the enum literal", async () => {
    await getAdminComplianceProducts({ compliance_status: "banned" });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      "/admin/compliance/products?compliance_status=banned",
    );
  });

  it("omits filters that are undefined", async () => {
    await getAdminComplianceProducts({
      limit: 10,
      offset: undefined,
      q: undefined,
      compliance_status: undefined,
      allowed_for_sale: undefined,
      is_active: undefined,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?limit=10");
  });

  it("combines all filters correctly in a single query string", async () => {
    await getAdminComplianceProducts({
      limit: 0,
      offset: 0,
      q: "  milk  ",
      allowed_for_sale: false,
      is_active: false,
      compliance_status: "restricted",
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    // URLSearchParams emits in insertion order. api.ts controls that
    // order: limit, offset, q, compliance_status, allowed_for_sale,
    // is_active.
    expect(path).toBe(
      "/admin/compliance/products?" +
        "limit=0" +
        "&offset=0" +
        "&q=milk" +
        "&compliance_status=restricted" +
        "&allowed_for_sale=false" +
        "&is_active=false",
    );
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminComplianceProducts({ limit: 10 }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("never serialises store_id as a query param", async () => {
    // TypeScript already prevents `store_id` from existing on
    // AdminComplianceProductsFilters; this test pins the runtime
    // guarantee for callers that might bypass the type via a raw
    // form input or `any`-typed spread.
    await getAdminComplianceProducts({
      // @ts-expect-error — store_id is intentionally not part of the
      // AdminComplianceProductsFilters contract (F2.20.0 §4).
      store_id: "10a233d4-63a7-41f3-aecb-41dfb8f58737",
      limit: 10,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/compliance/products?limit=10");
    expect(path).not.toMatch(/store_id/);
  });
});
