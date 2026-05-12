// F2.8.1: API-layer unit tests for products.
//
// Strategy: stub `@/api` so every call to the products API resolves
// against a controlled `apiRequest` mock. We assert URL, HTTP method,
// query string and body payload — exactly what the wire contract
// guarantees. No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  createProduct,
  createProductVariant,
  deleteProduct,
  deleteProductVariant,
  getProduct,
  getProductComplianceAudit,
  getProductSellable,
  getProductVariants,
  listProducts,
  updateProduct,
  updateProductCompliance,
  updateProductVariant,
} from "./api";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "22222222-2222-2222-2222-222222222222";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// listProducts
// --------------------------------------------------------------------- //

describe("listProducts", () => {
  it("calls GET /products with no query string when no filters provided", async () => {
    await listProducts();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe("/products");
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("appends every provided filter to the query string", async () => {
    await listProducts({
      only_active: true,
      only_sellable: false,
      compliance_status: "restricted",
      category: "vape",
      limit: 25,
      offset: 50,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      "/products?only_active=true&only_sellable=false" +
        "&compliance_status=restricted&category=vape&limit=25&offset=50",
    );
  });

  it("omits filters that are undefined", async () => {
    await listProducts({ only_active: true });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/products?only_active=true");
    expect(path).not.toMatch(/only_sellable/);
    expect(path).not.toMatch(/compliance_status/);
    expect(path).not.toMatch(/category/);
    expect(path).not.toMatch(/limit/);
    expect(path).not.toMatch(/offset/);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await listProducts({ limit: 10 }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// getProduct
// --------------------------------------------------------------------- //

describe("getProduct", () => {
  it("calls GET /products/{product_id}", async () => {
    await getProduct({ productId: PRODUCT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}`);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getProduct({ productId: PRODUCT_ID }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// getProductVariants
// --------------------------------------------------------------------- //

describe("getProductVariants", () => {
  it("calls GET /products/{product_id}/variants without query when only_active omitted", async () => {
    await getProductVariants({ productId: PRODUCT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}/variants`);
    expect(path).not.toMatch(/only_active/);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("appends only_active when provided", async () => {
    await getProductVariants({ productId: PRODUCT_ID, only_active: true });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/products/${PRODUCT_ID}/variants?only_active=true`);
  });
});

// --------------------------------------------------------------------- //
// getProductSellable
// --------------------------------------------------------------------- //

describe("getProductSellable", () => {
  it("calls GET /products/{product_id}/sellable", async () => {
    await getProductSellable({ productId: PRODUCT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}/sellable`);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// createProduct
// --------------------------------------------------------------------- //

describe("createProduct", () => {
  it("calls POST /products with the request body verbatim", async () => {
    await createProduct({
      body: {
        name: "Cosmic Gummies",
        category: "edibles",
        brand: "Lunar Co.",
        description: "Ten-pack, mixed flavours.",
      },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe("/products");
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({
      name: "Cosmic Gummies",
      category: "edibles",
      brand: "Lunar Co.",
      description: "Ten-pack, mixed flavours.",
    });
  });

  it("passes through optional compliance fields when provided", async () => {
    await createProduct({
      body: {
        name: "Restricted Tincture",
        category: "tinctures",
        compliance_status: "restricted",
        allowed_for_sale: true,
        jurisdiction: "CA",
      },
    });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({
      name: "Restricted Tincture",
      category: "tinctures",
      compliance_status: "restricted",
      allowed_for_sale: true,
      jurisdiction: "CA",
    });
  });
});

// --------------------------------------------------------------------- //
// updateProduct
// --------------------------------------------------------------------- //

describe("updateProduct", () => {
  it("calls PATCH /products/{product_id} with the partial body", async () => {
    await updateProduct({
      productId: PRODUCT_ID,
      body: { name: "Renamed Product", is_active: true },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({
      name: "Renamed Product",
      is_active: true,
    });
  });
});

// --------------------------------------------------------------------- //
// deleteProduct
// --------------------------------------------------------------------- //

describe("deleteProduct", () => {
  it("calls DELETE /products/{product_id} with no query when hard omitted (soft delete)", async () => {
    await deleteProduct({ productId: PRODUCT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}`);
    expect(path).not.toMatch(/hard/);
    expect(options?.method).toBe("DELETE");
    expect(options?.body).toBeUndefined();
  });

  it("appends ?hard=true when explicitly hard-deleting", async () => {
    await deleteProduct({ productId: PRODUCT_ID, hard: true });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/products/${PRODUCT_ID}?hard=true`);
    expect(options?.method).toBe("DELETE");
  });

  it("appends ?hard=false when explicitly soft-deleting", async () => {
    await deleteProduct({ productId: PRODUCT_ID, hard: false });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/products/${PRODUCT_ID}?hard=false`);
  });
});

// --------------------------------------------------------------------- //
// createProductVariant
// --------------------------------------------------------------------- //

describe("createProductVariant", () => {
  it("calls POST /products/{product_id}/variants with the request body", async () => {
    await createProductVariant({
      productId: PRODUCT_ID,
      body: {
        product_id: PRODUCT_ID,
        sku: "GUM-MIX-10",
        flavor: "mixed",
        price: "12.50",
      },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}/variants`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({
      product_id: PRODUCT_ID,
      sku: "GUM-MIX-10",
      flavor: "mixed",
      price: "12.50",
    });
  });

  it("preserves Decimal-as-string price/cost values verbatim (no number coercion)", async () => {
    await createProductVariant({
      productId: PRODUCT_ID,
      body: {
        product_id: PRODUCT_ID,
        sku: "GUM-MIX-20",
        price: "24.99",
        cost: "9.30",
      },
    });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const body = options?.body as { price: unknown; cost: unknown };
    expect(typeof body.price).toBe("string");
    expect(typeof body.cost).toBe("string");
    expect(body.price).toBe("24.99");
    expect(body.cost).toBe("9.30");
  });
});

// --------------------------------------------------------------------- //
// updateProductVariant
// --------------------------------------------------------------------- //

describe("updateProductVariant", () => {
  it("calls PATCH /variants/{variant_id} (NOT nested under /products)", async () => {
    await updateProductVariant({
      variantId: VARIANT_ID,
      body: { price: "15.00", is_active: false },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/variants/${VARIANT_ID}`);
    expect(path).not.toMatch(/\/products\//);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({ price: "15.00", is_active: false });
  });
});

// --------------------------------------------------------------------- //
// deleteProductVariant
// --------------------------------------------------------------------- //

describe("deleteProductVariant", () => {
  it("calls DELETE /variants/{variant_id} with no query when hard omitted", async () => {
    await deleteProductVariant({ variantId: VARIANT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/variants/${VARIANT_ID}`);
    expect(path).not.toMatch(/hard/);
    expect(path).not.toMatch(/\/products\//);
    expect(options?.method).toBe("DELETE");
  });

  it("appends ?hard=true when explicitly hard-deleting", async () => {
    await deleteProductVariant({ variantId: VARIANT_ID, hard: true });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/variants/${VARIANT_ID}?hard=true`);
  });
});

// --------------------------------------------------------------------- //
// updateProductCompliance
// --------------------------------------------------------------------- //

describe("updateProductCompliance", () => {
  it("calls PATCH /products/{product_id}/compliance with the request body", async () => {
    await updateProductCompliance({
      productId: PRODUCT_ID,
      body: {
        compliance_status: "banned",
        allowed_for_sale: false,
        reason: "FDA recall notice 2026-04-18",
      },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}/compliance`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({
      compliance_status: "banned",
      allowed_for_sale: false,
      reason: "FDA recall notice 2026-04-18",
    });
  });
});

// --------------------------------------------------------------------- //
// getProductComplianceAudit
// --------------------------------------------------------------------- //

describe("getProductComplianceAudit", () => {
  it("calls GET /products/{product_id}/compliance-audit", async () => {
    await getProductComplianceAudit({ productId: PRODUCT_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/products/${PRODUCT_ID}/compliance-audit`);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getProductComplianceAudit(
      { productId: PRODUCT_ID },
      controller.signal,
    );

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});
