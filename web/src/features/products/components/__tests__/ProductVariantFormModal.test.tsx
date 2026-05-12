// F2.8.6: ProductVariantFormModal tests.
//
// Strategy: stub `../../hooks` so we can drive the create / update
// variant mutation per case. Two especially load-bearing assertions:
//
//   1. CREATE forwards `{ productId, body: Omit<…, "product_id"> }` —
//      product_id injection is the hook's job, not the form's.
//   2. EDIT preserves `price` / `cost` as STRINGS (no number coercion,
//      no precision loss).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ProductVariantFormModal } from "../ProductVariantFormModal";
import * as productsHooks from "../../hooks";
import type { ProductVariant } from "../../types";
import type { UpdateProductVariantParams } from "../../api";
import type { CreateVariantMutationVariables } from "../../hooks";

vi.mock("../../hooks", () => ({
  useCreateVariantMutation: vi.fn(),
  useUpdateVariantMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "22222222-2222-2222-2222-222222222222";

function makeVariant(overrides: Partial<ProductVariant> = {}): ProductVariant {
  return {
    id: VARIANT_ID,
    product_id: PRODUCT_ID,
    sku: "GUM-MIX-10",
    barcode: "0123456789",
    flavor: "mixed",
    size_label: "10ct",
    unit_count: 10,
    puff_count: null,
    thc_strength: null,
    price: "12.50",
    cost: "5.30",
    is_active: true,
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
  ProductVariant,
  Error,
  CreateVariantMutationVariables
> & { mutate: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<
    ProductVariant,
    Error,
    CreateVariantMutationVariables
  > & { mutate: ReturnType<typeof vi.fn> };
}

function makeUpdateMutation(o: MutationOverrides = {}): UseMutationResult<
  ProductVariant,
  Error,
  UpdateProductVariantParams
> & { mutate: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<
    ProductVariant,
    Error,
    UpdateProductVariantParams
  > & { mutate: ReturnType<typeof vi.fn> };
}

beforeEach(() => {
  vi.mocked(productsHooks.useCreateVariantMutation).mockReset();
  vi.mocked(productsHooks.useUpdateVariantMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Create
// --------------------------------------------------------------------- //

describe("ProductVariantFormModal — create mode", () => {
  it("seeds blank fields and disables submit until SKU + price are filled", () => {
    vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
      makeCreateMutation(),
    );

    render(
      <ProductVariantFormModal
        mode="create"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
      />,
    );

    expect(screen.getByTestId("variant-form-sku")).toHaveValue("");
    expect(screen.getByTestId("variant-form-price")).toHaveValue("");
    expect(screen.getByTestId("variant-create-submit")).toBeDisabled();
  });

  it("forwards { productId, body } with only the filled keys (no null noise)", () => {
    const mutation = makeCreateMutation();
    vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductVariantFormModal
        mode="create"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
      />,
    );

    fireEvent.change(screen.getByTestId("variant-form-sku"), {
      target: { value: "GUM-MIX-10" },
    });
    fireEvent.change(screen.getByTestId("variant-form-price"), {
      target: { value: "12.50" },
    });
    fireEvent.click(screen.getByTestId("variant-create-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        sku: "GUM-MIX-10",
        price: "12.50",
        is_active: true,
      },
    });
  });

  it("preserves Decimal-as-string price/cost values verbatim (no number coercion)", () => {
    const mutation = makeCreateMutation();
    vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductVariantFormModal
        mode="create"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
      />,
    );

    fireEvent.change(screen.getByTestId("variant-form-sku"), {
      target: { value: "GUM-MIX-20" },
    });
    fireEvent.change(screen.getByTestId("variant-form-price"), {
      target: { value: "24.99" },
    });
    fireEvent.change(screen.getByTestId("variant-form-cost"), {
      target: { value: "9.30" },
    });
    fireEvent.click(screen.getByTestId("variant-create-submit"));

    const args = mutation.mutate.mock.calls[0][0] as {
      body: { price: unknown; cost: unknown };
    };
    expect(typeof args.body.price).toBe("string");
    expect(typeof args.body.cost).toBe("string");
    expect(args.body.price).toBe("24.99");
    expect(args.body.cost).toBe("9.30");
  });

  it("shows backend error inline", () => {
    vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
      makeCreateMutation({
        isError: true,
        error: new ApiError({ status: 422, message: "duplicate sku" }),
      }),
    );

    render(
      <ProductVariantFormModal
        mode="create"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
      />,
    );

    expect(screen.getByTestId("variant-create-error")).toHaveTextContent(
      /duplicate sku/i,
    );
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
      makeCreateMutation({ isSuccess: true }),
    );

    render(
      <ProductVariantFormModal
        mode="create"
        open={true}
        onOpenChange={onOpenChange}
        productId={PRODUCT_ID}
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

describe("ProductVariantFormModal — edit mode", () => {
  it("seeds initial values from the current variant — including string price/cost", () => {
    vi.mocked(productsHooks.useUpdateVariantMutation).mockReturnValue(
      makeUpdateMutation(),
    );

    render(
      <ProductVariantFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
        variant={makeVariant()}
      />,
    );

    expect(screen.getByTestId("variant-form-sku")).toHaveValue("GUM-MIX-10");
    expect(screen.getByTestId("variant-form-barcode")).toHaveValue(
      "0123456789",
    );
    expect(screen.getByTestId("variant-form-price")).toHaveValue("12.50");
    expect(screen.getByTestId("variant-form-cost")).toHaveValue("5.30");
    expect(screen.getByTestId("variant-form-unit-count")).toHaveValue(10);
  });

  it("forwards { variantId, body } with full update payload (price/cost stay strings)", () => {
    const mutation = makeUpdateMutation();
    vi.mocked(productsHooks.useUpdateVariantMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductVariantFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
        variant={makeVariant()}
      />,
    );

    fireEvent.change(screen.getByTestId("variant-form-price"), {
      target: { value: "15.00" },
    });
    fireEvent.click(screen.getByTestId("variant-form-active-checkbox"));
    fireEvent.click(screen.getByTestId("variant-edit-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      variantId: VARIANT_ID,
      body: {
        sku: "GUM-MIX-10",
        barcode: "0123456789",
        flavor: "mixed",
        size_label: "10ct",
        thc_strength: null,
        unit_count: 10,
        puff_count: null,
        price: "15.00",
        cost: "5.30",
        is_active: false,
      },
    });

    // Defensive: still strings.
    const args = mutation.mutate.mock.calls[0][0] as {
      body: { price: unknown; cost: unknown };
    };
    expect(typeof args.body.price).toBe("string");
    expect(typeof args.body.cost).toBe("string");
  });

  it("shows backend error inline", () => {
    vi.mocked(productsHooks.useUpdateVariantMutation).mockReturnValue(
      makeUpdateMutation({
        isError: true,
        error: new ApiError({ status: 422, message: "invalid price" }),
      }),
    );

    render(
      <ProductVariantFormModal
        mode="edit"
        open={true}
        onOpenChange={vi.fn()}
        productId={PRODUCT_ID}
        variant={makeVariant()}
      />,
    );

    expect(screen.getByTestId("variant-edit-error")).toHaveTextContent(
      /invalid price/i,
    );
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useUpdateVariantMutation).mockReturnValue(
      makeUpdateMutation({ isSuccess: true }),
    );

    render(
      <ProductVariantFormModal
        mode="edit"
        open={true}
        onOpenChange={onOpenChange}
        productId={PRODUCT_ID}
        variant={makeVariant()}
      />,
    );

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
