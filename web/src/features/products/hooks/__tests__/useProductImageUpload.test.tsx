// F2.22.4.G: tests for the product image upload hook.
//
// The hook orchestrates three calls in order:
//   1. requestProductImageUploadUrl   (FastAPI)
//   2. uploadProductImageToSignedUrl  (Supabase Storage)
//   3. confirmProductImageUpload      (FastAPI metadata)
//
// We mock the storage api module so the test asserts ordering,
// short-circuit on upload failure, client-side validation, and
// query invalidation directly — no network calls, no real
// supabase-js calls.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import {
  PRODUCT_IMAGES_BUCKET,
  ProductImageUploadError,
} from "../../storage";
import { useProductImageUpload } from "../useProductImageUpload";
import { productsKeys } from "../queryKeys";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import * as storage from "../../storage";

vi.mock("../../storage", async () => {
  const actual = await vi.importActual<typeof storage>("../../storage");
  return {
    ...actual,
    requestProductImageUploadUrl: vi.fn(),
    uploadProductImageToSignedUrl: vi.fn(),
    confirmProductImageUpload: vi.fn(),
  };
});

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function wrap(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function makeFile({
  type = "image/jpeg",
  size = 1024,
  name = "hero.jpg",
}: { type?: string; size?: number; name?: string } = {}): File {
  const buf = new Uint8Array(size);
  return new File([buf], name, { type });
}

beforeEach(() => {
  vi.mocked(storage.requestProductImageUploadUrl).mockReset();
  vi.mocked(storage.uploadProductImageToSignedUrl).mockReset();
  vi.mocked(storage.confirmProductImageUpload).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useProductImageUpload — happy path", () => {
  it("calls upload-url → uploadToSignedUrl → confirm in order", async () => {
    const order: string[] = [];
    vi.mocked(storage.requestProductImageUploadUrl).mockImplementation(
      async () => {
        order.push("upload-url");
        return {
          bucket: PRODUCT_IMAGES_BUCKET,
          object_key: `products/${PRODUCT_ID}/abc.jpg`,
          signed_upload_url: "https://example.supabase.co/x?token=t",
          expires_in_seconds: 600,
        };
      },
    );
    vi.mocked(storage.uploadProductImageToSignedUrl).mockImplementation(
      async () => {
        order.push("supabase-upload");
      },
    );
    vi.mocked(storage.confirmProductImageUpload).mockImplementation(
      async () => {
        order.push("confirm");
        return {
          id: "img-1",
          product_id: PRODUCT_ID,
          object_key: `products/${PRODUCT_ID}/abc.jpg`,
          public_url: null,
          uploaded_by_user_id: "admin-1",
          created_at: "2026-05-27T00:00:00Z",
          updated_at: "2026-05-27T00:00:00Z",
        };
      },
    );

    const client = makeClient();
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({ file: makeFile() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(order).toEqual([
      "upload-url",
      "supabase-upload",
      "confirm",
    ]);

    expect(
      vi.mocked(storage.confirmProductImageUpload),
    ).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        bucket: PRODUCT_IMAGES_BUCKET,
        object_key: `products/${PRODUCT_ID}/abc.jpg`,
      },
    });
  });

  it("invalidates product detail, product lists, and admin-products lists on success", async () => {
    vi.mocked(storage.requestProductImageUploadUrl).mockResolvedValue({
      bucket: PRODUCT_IMAGES_BUCKET,
      object_key: `products/${PRODUCT_ID}/abc.jpg`,
      signed_upload_url: "https://example.supabase.co/x?token=t",
      expires_in_seconds: 600,
    });
    vi.mocked(storage.uploadProductImageToSignedUrl).mockResolvedValue();
    vi.mocked(storage.confirmProductImageUpload).mockResolvedValue({
      id: "img-1",
      product_id: PRODUCT_ID,
      object_key: `products/${PRODUCT_ID}/abc.jpg`,
      public_url: null,
      uploaded_by_user_id: "admin-1",
      created_at: "2026-05-27T00:00:00Z",
      updated_at: "2026-05-27T00:00:00Z",
    });

    const client = makeClient();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({ file: makeFile() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = spy.mock.calls.map((args) => args[0]?.queryKey);
    expect(keys).toContainEqual(productsKeys.detail(PRODUCT_ID));
    expect(keys).toContainEqual(productsKeys.lists());
    expect(keys).toContainEqual(adminProductsQueryKeys.lists());
  });
});

describe("useProductImageUpload — failure paths", () => {
  it("does NOT call confirm when Supabase upload fails", async () => {
    vi.mocked(storage.requestProductImageUploadUrl).mockResolvedValue({
      bucket: PRODUCT_IMAGES_BUCKET,
      object_key: `products/${PRODUCT_ID}/abc.jpg`,
      signed_upload_url: "https://example.supabase.co/x?token=t",
      expires_in_seconds: 600,
    });
    vi.mocked(storage.uploadProductImageToSignedUrl).mockRejectedValue(
      new ProductImageUploadError("upload failed"),
    );

    const client = makeClient();
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({ file: makeFile() });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(
      vi.mocked(storage.confirmProductImageUpload),
    ).not.toHaveBeenCalled();
  });

  it("rejects invalid content type before any backend call", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({ file: makeFile({ type: "image/gif" }) });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(
      vi.mocked(storage.requestProductImageUploadUrl),
    ).not.toHaveBeenCalled();
    expect(
      vi.mocked(storage.uploadProductImageToSignedUrl),
    ).not.toHaveBeenCalled();
    expect(
      vi.mocked(storage.confirmProductImageUpload),
    ).not.toHaveBeenCalled();
  });

  it("rejects oversized files before any backend call", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({
      file: makeFile({ size: 6 * 1024 * 1024 }),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(
      vi.mocked(storage.requestProductImageUploadUrl),
    ).not.toHaveBeenCalled();
  });

  it("rejects empty files before any backend call", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useProductImageUpload(PRODUCT_ID),
      { wrapper: wrap(client) },
    );

    result.current.mutate({ file: makeFile({ size: 0 }) });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(
      vi.mocked(storage.requestProductImageUploadUrl),
    ).not.toHaveBeenCalled();
  });
});
