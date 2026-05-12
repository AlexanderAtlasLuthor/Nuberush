// F2.8.6: DeactivateVariantDialog tests.
//
// Pins the soft-delete contract:
//   - mutate is called with `{ variantId, productId, hard: false }` —
//     productId is needed for the hook's invalidation, even though the
//     wire only carries variantId.
//   - inline backend error on failure.
//   - auto-close on success.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { DeactivateVariantDialog } from "../DeactivateVariantDialog";
import * as productsHooks from "../../hooks";
import type { ProductVariant } from "../../types";
import type { DeleteVariantMutationVariables } from "../../hooks";

vi.mock("../../hooks", () => ({
  useDeleteVariantMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "22222222-2222-2222-2222-222222222222";

function makeVariant(overrides: Partial<ProductVariant> = {}): ProductVariant {
  return {
    id: VARIANT_ID,
    product_id: PRODUCT_ID,
    sku: "GUM-MIX-10",
    barcode: null,
    flavor: null,
    size_label: null,
    unit_count: null,
    puff_count: null,
    thc_strength: null,
    price: "12.50",
    cost: null,
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

function makeMutation(o: MutationOverrides = {}): UseMutationResult<
  void,
  Error,
  DeleteVariantMutationVariables
> & { mutate: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<
    void,
    Error,
    DeleteVariantMutationVariables
  > & { mutate: ReturnType<typeof vi.fn> };
}

beforeEach(() => {
  vi.mocked(productsHooks.useDeleteVariantMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DeactivateVariantDialog", () => {
  it("renders a Deactivate (not Delete) destructive button", () => {
    vi.mocked(productsHooks.useDeleteVariantMutation).mockReturnValue(
      makeMutation(),
    );

    render(
      <DeactivateVariantDialog
        open={true}
        onOpenChange={vi.fn()}
        variant={makeVariant()}
      />,
    );

    const submit = screen.getByTestId("deactivate-variant-submit");
    expect(submit).toHaveTextContent(/deactivate/i);
    expect(submit).not.toHaveTextContent(/delete/i);
  });

  it("calls deleteProductVariant with { variantId, productId, hard: false }", () => {
    const mutation = makeMutation();
    vi.mocked(productsHooks.useDeleteVariantMutation).mockReturnValue(
      mutation,
    );

    render(
      <DeactivateVariantDialog
        open={true}
        onOpenChange={vi.fn()}
        variant={makeVariant()}
      />,
    );

    fireEvent.click(screen.getByTestId("deactivate-variant-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      variantId: VARIANT_ID,
      productId: PRODUCT_ID,
      hard: false,
    });
    // Defensive: never hard:true.
    const args = mutation.mutate.mock.calls[0][0] as DeleteVariantMutationVariables;
    expect(args.hard).toBe(false);
  });

  it("disables the submit button while pending", () => {
    vi.mocked(productsHooks.useDeleteVariantMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <DeactivateVariantDialog
        open={true}
        onOpenChange={vi.fn()}
        variant={makeVariant()}
      />,
    );

    const submit = screen.getByTestId("deactivate-variant-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/deactivating/i);
  });

  it("shows backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useDeleteVariantMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 409, message: "variant in use" }),
      }),
    );

    render(
      <DeactivateVariantDialog
        open={true}
        onOpenChange={onOpenChange}
        variant={makeVariant()}
      />,
    );

    expect(screen.getByTestId("deactivate-variant-error")).toHaveTextContent(
      /variant in use/i,
    );
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useDeleteVariantMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    render(
      <DeactivateVariantDialog
        open={true}
        onOpenChange={onOpenChange}
        variant={makeVariant()}
      />,
    );

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
