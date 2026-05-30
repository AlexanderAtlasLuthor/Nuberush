// F2.8.6: ProductFormModal tests.
//
// Strategy: stub `../../hooks` so we can drive the create / update
// mutation state per case. The modal is rendered directly (open=true)
// to exercise initial values, payload composition, error UX, and
// close-on-success without involving the full page wiring.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ProductFormModal } from "../ProductFormModal";
import * as productsHooks from "../../hooks";
import type { Product } from "../../types";
import type {
  CreateProductParams,
  UpdateProductParams,
} from "../../api";

vi.mock("../../hooks", () => ({
  useCreateProductMutation: vi.fn(),
  useUpdateProductMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Cosmic Gummies",
    brand: "Lunar Co.",
    category: "edibles",
    description: "ten pack",
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    approval_status: "approved",
    proposed_by_store_id: null,
    proposed_by_user_id: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

interface MutationOverrides {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
}

function makeCreateMutation(o: MutationOverrides = {}): UseMutationResult<
  Product,
  Error,
  CreateProductParams
> & { mutate: ReturnType<typeof vi.fn> } {
  const mutate = vi.fn();
  return {
    mutate,
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<Product, Error, CreateProductParams> & {
    mutate: ReturnType<typeof vi.fn>;
  };
}

function makeUpdateMutation(o: MutationOverrides = {}): UseMutationResult<
  Product,
  Error,
  UpdateProductParams
> & { mutate: ReturnType<typeof vi.fn> } {
  const mutate = vi.fn();
  return {
    mutate,
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<Product, Error, UpdateProductParams> & {
    mutate: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(productsHooks.useCreateProductMutation).mockReset();
  vi.mocked(productsHooks.useUpdateProductMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Create
// --------------------------------------------------------------------- //

describe("ProductFormModal — create mode", () => {
  it("seeds blank fields and disables submit until name + category are filled", () => {
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      makeCreateMutation(),
    );

    render(
      <ProductFormModal mode="create" open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByTestId("product-form-name")).toHaveValue("");
    expect(screen.getByTestId("product-form-category")).toHaveValue("");
    expect(screen.getByTestId("product-form-jurisdiction")).toHaveValue("FL");
    expect(screen.getByTestId("product-create-submit")).toBeDisabled();
  });

  it("forwards the exact ProductCreateRequest payload (only filled fields)", () => {
    const mutation = makeCreateMutation();
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductFormModal mode="create" open={true} onOpenChange={vi.fn()} />,
    );

    fireEvent.change(screen.getByTestId("product-form-name"), {
      target: { value: "  Cosmic Gummies  " },
    });
    fireEvent.change(screen.getByTestId("product-form-category"), {
      target: { value: "edibles" },
    });
    fireEvent.click(screen.getByTestId("product-create-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      body: {
        name: "Cosmic Gummies",
        category: "edibles",
        brand: undefined,
        description: undefined,
        jurisdiction: "FL",
        compliance_status: "allowed",
        allowed_for_sale: true,
      },
    });
  });

  it("permits banned + allowed_for_sale=true and forwards verbatim", () => {
    const mutation = makeCreateMutation();
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductFormModal mode="create" open={true} onOpenChange={vi.fn()} />,
    );

    fireEvent.change(screen.getByTestId("product-form-name"), {
      target: { value: "Restricted Item" },
    });
    fireEvent.change(screen.getByTestId("product-form-category"), {
      target: { value: "tinctures" },
    });

    // Switch compliance Select → banned. Allowed checkbox stays checked
    // (default true) — UI does NOT auto-flip.
    fireEvent.click(
      screen.getByTestId("product-create-compliance-trigger"),
    );
    fireEvent.click(screen.getByRole("option", { name: /banned/i }));

    expect(
      screen.getByTestId("product-create-allowed-checkbox"),
    ).toHaveAttribute("aria-checked", "true");

    fireEvent.click(screen.getByTestId("product-create-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      body: expect.objectContaining({
        compliance_status: "banned",
        allowed_for_sale: true,
      }),
    });
  });

  it("disables submit while pending", () => {
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      makeCreateMutation({ isPending: true }),
    );

    render(
      <ProductFormModal mode="create" open={true} onOpenChange={vi.fn()} />,
    );

    fireEvent.change(screen.getByTestId("product-form-name"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("product-form-category"), {
      target: { value: "Y" },
    });

    const submit = screen.getByTestId("product-create-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/creating/i);
  });

  it("shows the backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      makeCreateMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "category cannot be empty",
        }),
      }),
    );

    render(
      <ProductFormModal
        mode="create"
        open={true}
        onOpenChange={onOpenChange}
      />,
    );

    expect(screen.getByTestId("product-create-error")).toHaveTextContent(
      /category cannot be empty/i,
    );
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useCreateProductMutation).mockReturnValue(
      makeCreateMutation({ isSuccess: true }),
    );

    render(
      <ProductFormModal
        mode="create"
        open={true}
        onOpenChange={onOpenChange}
      />,
    );

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});

// --------------------------------------------------------------------- //
// Edit
// --------------------------------------------------------------------- //

describe("ProductFormModal — edit mode", () => {
  it("seeds initial values from the current product", () => {
    vi.mocked(productsHooks.useUpdateProductMutation).mockReturnValue(
      makeUpdateMutation(),
    );

    render(
      <ProductFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct({
          name: "Cosmic Gummies",
          brand: "Lunar Co.",
          category: "edibles",
          description: "ten pack",
          jurisdiction: "FL",
          is_active: true,
        })}
      />,
    );

    expect(screen.getByTestId("product-form-name")).toHaveValue(
      "Cosmic Gummies",
    );
    expect(screen.getByTestId("product-form-brand")).toHaveValue(
      "Lunar Co.",
    );
    expect(screen.getByTestId("product-form-category")).toHaveValue(
      "edibles",
    );
    expect(screen.getByTestId("product-form-description")).toHaveValue(
      "ten pack",
    );
    expect(screen.getByTestId("product-form-jurisdiction")).toHaveValue("FL");
    expect(
      screen.getByTestId("product-edit-active-checkbox"),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("forwards the exact ProductUpdateRequest payload", () => {
    const mutation = makeUpdateMutation();
    vi.mocked(productsHooks.useUpdateProductMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct()}
      />,
    );

    // Change the name and toggle is_active; leave everything else as-is.
    fireEvent.change(screen.getByTestId("product-form-name"), {
      target: { value: "Renamed" },
    });
    fireEvent.click(screen.getByTestId("product-edit-active-checkbox"));
    fireEvent.click(screen.getByTestId("product-edit-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        name: "Renamed",
        brand: "Lunar Co.",
        category: "edibles",
        description: "ten pack",
        jurisdiction: "FL",
        is_active: false,
      },
    });
  });

  it("shows backend error inline", () => {
    vi.mocked(productsHooks.useUpdateProductMutation).mockReturnValue(
      makeUpdateMutation({
        isError: true,
        error: new ApiError({ status: 409, message: "name conflict" }),
      }),
    );

    render(
      <ProductFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct()}
      />,
    );

    expect(screen.getByTestId("product-edit-error")).toHaveTextContent(
      /name conflict/i,
    );
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useUpdateProductMutation).mockReturnValue(
      makeUpdateMutation({ isSuccess: true }),
    );

    render(
      <ProductFormModal
        mode="edit"
        open={true}
        onOpenChange={onOpenChange}
        product={makeProduct()}
      />,
    );

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
