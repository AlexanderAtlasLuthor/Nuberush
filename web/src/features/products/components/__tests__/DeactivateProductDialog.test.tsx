// F2.8.6: DeactivateProductDialog tests.
//
// Pins the soft-delete contract:
//   - mutate is called with `{ productId, hard: false }` — never `true`.
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
import { DeactivateProductDialog } from "../DeactivateProductDialog";
import * as productsHooks from "../../hooks";
import type { Product } from "../../types";
import type { DeleteProductParams } from "../../api";

vi.mock("../../hooks", () => ({
  useDeleteProductMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Cosmic Gummies",
    brand: "Lunar Co.",
    category: "edibles",
    description: null,
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

function makeMutation(o: MutationOverrides = {}): UseMutationResult<
  void,
  Error,
  DeleteProductParams
> & { mutate: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<void, Error, DeleteProductParams> & {
    mutate: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(productsHooks.useDeleteProductMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DeactivateProductDialog", () => {
  it("renders a Deactivate (not Delete) destructive button", () => {
    vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
      makeMutation(),
    );

    render(
      <DeactivateProductDialog
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct()}
      />,
    );

    const submit = screen.getByTestId("deactivate-product-submit");
    expect(submit).toHaveTextContent(/deactivate/i);
    expect(submit).not.toHaveTextContent(/delete/i);
  });

  it("calls deleteProduct with hard:false (soft delete)", () => {
    const mutation = makeMutation();
    vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
      mutation,
    );

    render(
      <DeactivateProductDialog
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct()}
      />,
    );

    fireEvent.click(screen.getByTestId("deactivate-product-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      hard: false,
    });
    // Defensive: never hard:true.
    const args = mutation.mutate.mock.calls[0][0] as DeleteProductParams;
    expect(args.hard).toBe(false);
  });

  it("disables the submit button while pending", () => {
    vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <DeactivateProductDialog
        open={true}
        onOpenChange={vi.fn()}
        product={makeProduct()}
      />,
    );

    const submit = screen.getByTestId("deactivate-product-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/deactivating/i);
  });

  it("shows backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 403, message: "Admin only" }),
      }),
    );

    render(
      <DeactivateProductDialog
        open={true}
        onOpenChange={onOpenChange}
        product={makeProduct()}
      />,
    );

    expect(screen.getByTestId("deactivate-product-error")).toHaveTextContent(
      /admin only/i,
    );
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    render(
      <DeactivateProductDialog
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
