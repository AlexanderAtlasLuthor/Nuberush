// F2.11-M2.4: tests for CreateOrderPage.
//
// The create page may manage local form state, but the backend remains
// authoritative for totals, stock effects, sellability, tenancy, and
// order validity. These tests validate UI state and mutation payloads.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  MemoryRouter,
  Route,
  Routes,
  useParams,
} from "react-router-dom";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import * as auth from "@/auth";
import * as inventoryHooks from "@/features/inventory/hooks";
import type {
  InventoryItem,
  InventoryListResponse,
} from "@/features/inventory/types";
import CreateOrderPage from "../CreateOrderPage";
import type { CreateOrderParams } from "../../api";
import * as ordersHooks from "../../hooks";
import type { OrderRead } from "../../types";

vi.mock("@/auth", () => ({
  useStoreContext: vi.fn(),
}));

vi.mock("../../hooks", () => ({
  useCreateOrderMutation: vi.fn(),
}));

vi.mock("@/features/inventory/hooks", () => ({
  useInventoryList: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const ORDER_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const INVENTORY_ITEM_ID = "44444444-4444-4444-4444-444444444444";
const IDEMPOTENCY_KEY = "99999999-9999-4999-8999-999999999999";

interface MutationOverrides {
  data?: OrderRead;
  error?: Error | null;
  isError?: boolean;
  isPending?: boolean;
  isSuccess?: boolean;
}

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeMutation(
  overrides: MutationOverrides = {},
): UseMutationResult<OrderRead, Error, CreateOrderParams> & {
  mutate: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
} {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    data: overrides.data,
    error: overrides.error ?? null,
    isError: overrides.isError ?? false,
    isPending: overrides.isPending ?? false,
    isSuccess: overrides.isSuccess ?? false,
  } as unknown as UseMutationResult<OrderRead, Error, CreateOrderParams> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_ID,
    customer_user_id: null,
    idempotency_key: IDEMPOTENCY_KEY,
    status: "pending",
    subtotal_amount: "0.00",
    tax_amount: "0.00",
    total_amount: "0.00",
    age_verified_at: null,
    age_verified_by_user_id: null,
    accepted_at: null,
    canceled_at: null,
    delivered_at: null,
    returned_at: null,
    cancel_reason: null,
    notes: null,
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    items: [],
    ...overrides,
  };
}

function makeInventoryItem(
  overrides: Partial<InventoryItem> = {},
): InventoryItem {
  return {
    id: INVENTORY_ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 12,
    quantity_reserved: 2,
    reorder_threshold: 4,
    status: "available",
    last_counted_at: null,
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: "Mixed berry",
      size_label: "10 pack",
      is_active: true,
      product: {
        id: "55555555-5555-5555-5555-555555555555",
        name: "Cosmic Gummies",
        brand: "Orbit",
        category: "edibles",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      },
    },
    ...overrides,
  };
}

function makeInventoryListResponse(
  overrides: Partial<InventoryListResponse> = {},
): InventoryListResponse {
  return {
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
    ...overrides,
  };
}

function mockStore(currentStoreId: string | null = STORE_ID) {
  vi.mocked(auth.useStoreContext).mockReturnValue({
    currentStoreId,
  } as ReturnType<typeof auth.useStoreContext>);
}

function mockCreateMutation(
  mutation: ReturnType<typeof makeMutation> = makeMutation(),
) {
  vi.mocked(ordersHooks.useCreateOrderMutation).mockReturnValue(mutation);
  return mutation;
}

function mockInventoryQuery(
  partial: Partial<UseQueryResult<InventoryListResponse>>,
) {
  vi.mocked(inventoryHooks.useInventoryList).mockReturnValue(
    asQueryResult<InventoryListResponse>(partial),
  );
}

function CreatedOrderRoute() {
  const params = useParams<{ orderId: string }>();
  return <div data-testid="created-order-route">{params.orderId}</div>;
}

function pageTree() {
  return (
    <MemoryRouter initialEntries={["/app/store/orders/new"]}>
      <Routes>
        <Route path="/app/store/orders/new" element={<CreateOrderPage />} />
        <Route path="/app/store/orders" element={<div data-testid="orders-index" />} />
        <Route path="/app/store/orders/:orderId" element={<CreatedOrderRoute />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderPage() {
  return render(pageTree());
}

function addDefaultVariant() {
  fireEvent.click(screen.getByTestId(`create-order-picker-add-${VARIANT_ID}`));
}

async function readRuntimeSource(filename: string): Promise<string> {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const here = path.resolve(__dirname, "..", filename);
  const source = fs.readFileSync(here, "utf-8");

  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");
}

let randomUUIDMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.mocked(auth.useStoreContext).mockReset();
  vi.mocked(ordersHooks.useCreateOrderMutation).mockReset();
  vi.mocked(inventoryHooks.useInventoryList).mockReset();

  randomUUIDMock = vi.fn(() => IDEMPOTENCY_KEY);
  vi.stubGlobal("crypto", {
    randomUUID: randomUUIDMock,
  });

  mockStore();
  mockCreateMutation();
  mockInventoryQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeInventoryListResponse({
      items: [makeInventoryItem()],
      total: 1,
    }),
    error: null,
    refetch: vi.fn() as never,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("CreateOrderPage - store and navigation", () => {
  it("renders the no-store empty state without the order form", () => {
    mockStore(null);

    renderPage();

    expect(screen.getByText(/no store selected/i)).toBeInTheDocument();
    expect(
      screen.getByText(/order creation operates inside a store context/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^create order$/i })).toBeNull();
    expect(screen.queryByText(/variant picker/i)).toBeNull();
  });

  it("links back to orders and the Cancel button navigates to /app/store/orders", () => {
    renderPage();

    expect(screen.getByTestId("create-order-back")).toHaveAttribute(
      "href",
      "/app/store/orders",
    );

    fireEvent.click(screen.getByTestId("create-order-cancel"));
    expect(screen.getByTestId("orders-index")).toBeInTheDocument();
  });

  it("generates one stable idempotency key across rerenders and submits it", () => {
    const mutation = mockCreateMutation();
    renderPage();

    addDefaultVariant();
    fireEvent.change(screen.getByLabelText(/^notes$/i), {
      target: { value: "  first note  " },
    });
    fireEvent.change(screen.getByLabelText(/^notes$/i), {
      target: { value: "  updated note  " },
    });
    fireEvent.click(screen.getByTestId("create-order-submit"));

    expect(randomUUIDMock).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      body: {
        idempotency_key: IDEMPOTENCY_KEY,
        items: [{ variant_id: VARIANT_ID, quantity: 1 }],
        notes: "updated note",
      },
    });
  });
});

describe("CreateOrderPage - variant picker states", () => {
  it("renders the variant catalog loading state", () => {
    mockInventoryQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/loading variants/i);
  });

  it("renders variant catalog backend ApiError detail and wires Retry to refetch", () => {
    const refetch = vi.fn();
    mockInventoryQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError({
        status: 500,
        message: "inventory picker unavailable",
      }),
      refetch: refetch as never,
    });

    renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent(
      /variants failed to load/i,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /inventory picker unavailable/i,
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the variant catalog empty state", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeInventoryListResponse({ items: [], total: 0 }),
      error: null,
    });

    renderPage();

    expect(screen.getByText(/no inventory in this store/i)).toBeInTheDocument();
    expect(
      screen.getByText(/there are no variants to pick from yet/i),
    ).toBeInTheDocument();
  });

  it("renders no-matches copy when the current-page search has no match", () => {
    renderPage();

    fireEvent.change(screen.getByTestId("create-order-picker-search"), {
      target: { value: "not-on-this-page" },
    });

    expect(screen.getByText(/no matches/i)).toBeInTheDocument();
    expect(
      screen.getByText(/no variants on this page match "not-on-this-page"/i),
    ).toBeInTheDocument();
  });

  it("lists backend variant rows in the picker", () => {
    renderPage();

    expect(screen.getByText("Cosmic Gummies")).toBeInTheDocument();
    expect(screen.getByText("GUM-MIX-10")).toBeInTheDocument();
    expect(screen.getByText(/mixed berry/i)).toBeInTheDocument();
    expect(screen.getByText(/10 pack/i)).toBeInTheDocument();
    expect(screen.getByText("available")).toBeInTheDocument();
    expect(screen.getByText("allowed")).toBeInTheDocument();
    expect(screen.getByTestId("create-order-picker-total")).toHaveTextContent(
      /1 variants/i,
    );
  });
});

describe("CreateOrderPage - line editing", () => {
  it("selecting a variant adds an order line", () => {
    renderPage();

    addDefaultVariant();

    const quantity = screen.getByTestId("create-order-line-quantity-0");
    expect(quantity).toHaveValue(1);
    expect(screen.getByTestId("create-order-line-remove-0")).toBeInTheDocument();
  });

  it("adding the same variant again merges into one line and increments quantity", () => {
    renderPage();

    addDefaultVariant();
    addDefaultVariant();

    expect(screen.getAllByTestId(/create-order-line-quantity-/)).toHaveLength(1);
    expect(screen.getByTestId("create-order-line-quantity-0")).toHaveValue(2);
  });

  it("quantity edits update the submitted payload", () => {
    const mutation = mockCreateMutation();
    renderPage();

    addDefaultVariant();
    fireEvent.change(screen.getByTestId("create-order-line-quantity-0"), {
      target: { value: "4" },
    });
    fireEvent.click(screen.getByTestId("create-order-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      body: {
        idempotency_key: IDEMPOTENCY_KEY,
        items: [{ variant_id: VARIANT_ID, quantity: 4 }],
        notes: null,
      },
    });
  });

  it("remove deletes the line and returns submit to disabled", () => {
    renderPage();

    addDefaultVariant();
    expect(screen.getByTestId("create-order-submit")).not.toBeDisabled();

    fireEvent.click(screen.getByTestId("create-order-line-remove-0"));

    expect(screen.getByText(/no items yet/i)).toBeInTheDocument();
    expect(screen.getByTestId("create-order-submit")).toBeDisabled();
  });

  it("submit is disabled with no items or an invalid quantity", () => {
    renderPage();

    expect(screen.getByTestId("create-order-submit")).toBeDisabled();

    addDefaultVariant();
    fireEvent.change(screen.getByTestId("create-order-line-quantity-0"), {
      target: { value: "0" },
    });

    expect(screen.getByTestId("create-order-submit")).toBeDisabled();
  });
});

describe("CreateOrderPage - submit payload and server feedback", () => {
  it("submits exact payload shape, strips display-only fields, and converts whitespace notes to null", () => {
    const mutation = mockCreateMutation();
    renderPage();

    addDefaultVariant();
    fireEvent.change(screen.getByLabelText(/^notes$/i), {
      target: { value: "    " },
    });
    fireEvent.click(screen.getByTestId("create-order-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      body: {
        idempotency_key: IDEMPOTENCY_KEY,
        items: [{ variant_id: VARIANT_ID, quantity: 1 }],
        notes: null,
      },
    });

    const payload = mutation.mutate.mock.calls[0][0] as CreateOrderParams;
    expect(Object.keys(payload.body.items[0]).sort()).toEqual([
      "quantity",
      "variant_id",
    ]);
  });

  it("trims non-empty notes before submit", () => {
    const mutation = mockCreateMutation();
    renderPage();

    addDefaultVariant();
    fireEvent.change(screen.getByLabelText(/^notes$/i), {
      target: { value: "  porch pickup  " },
    });
    fireEvent.click(screen.getByTestId("create-order-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      body: {
        idempotency_key: IDEMPOTENCY_KEY,
        items: [{ variant_id: VARIANT_ID, quantity: 1 }],
        notes: "porch pickup",
      },
    });
  });

  it("shows backend ApiError detail from the create mutation", () => {
    mockCreateMutation(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 409,
          message: "idempotency key reused with a different body",
        }),
      }),
    );

    renderPage();

    expect(screen.getByTestId("create-order-error")).toHaveTextContent(
      /idempotency key reused with a different body/i,
    );
  });

  it("navigates to the created order detail page when mutation reports success", async () => {
    mockCreateMutation(
      makeMutation({
        isSuccess: true,
        data: makeOrder({
          id: "88888888-8888-8888-8888-888888888888",
        }),
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("created-order-route")).toHaveTextContent(
        "88888888-8888-8888-8888-888888888888",
      );
    });
  });

  it("calls mutation.reset when the user edits the form after a backend error", () => {
    const mutation = makeMutation({
      isError: true,
      error: new ApiError({
        status: 422,
        message: "backend rejected create",
      }),
    });
    mockCreateMutation(mutation);
    renderPage();

    addDefaultVariant();
    fireEvent.change(screen.getByLabelText(/^notes$/i), {
      target: { value: "edited after error" },
    });

    expect(mutation.reset).toHaveBeenCalledTimes(2);
  });

  it("locks form controls and flips submit copy while pending", () => {
    const view = renderPage();

    addDefaultVariant();
    mockCreateMutation(makeMutation({ isPending: true }));
    view.rerender(pageTree());

    expect(screen.getByTestId("create-order-picker-search")).toBeDisabled();
    expect(screen.getByTestId("create-order-line-quantity-0")).toBeDisabled();
    expect(screen.getByTestId("create-order-line-remove-0")).toBeDisabled();
    expect(screen.getByLabelText(/^notes$/i)).toBeDisabled();
    expect(screen.getByTestId("create-order-cancel")).toBeDisabled();
    expect(screen.getByTestId("create-order-submit")).toBeDisabled();
    expect(screen.getByTestId("create-order-submit")).toHaveTextContent(
      /creating/i,
    );
  });
});

describe("CreateOrderPage - architecture", () => {
  it("does NOT import auth role checks, permission helpers, fetch, or axios", async () => {
    const code = await readRuntimeSource("CreateOrderPage.tsx");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buser\.role\b/);
    expect(code).not.toMatch(/\brole\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT compute authoritative order totals or own transition validity", async () => {
    const code = await readRuntimeSource("CreateOrderPage.tsx");

    expect(code).not.toMatch(/subtotal_amount\s*[-+*/]/);
    expect(code).not.toMatch(/tax_amount\s*[-+*/]/);
    expect(code).not.toMatch(/total_amount\s*[-+*/]/);
    expect(code).not.toMatch(/unit_price\s*[-+*/]/);
    expect(code).not.toMatch(/line_total\s*[-+*/]/);
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/isTransitionAllowed\s*\(/);
  });

  it("does NOT gate add or submit controls on stock/compliance authority", async () => {
    const code = await readRuntimeSource("CreateOrderPage.tsx");

    expect(code).not.toMatch(/disabled=\{[^}]*quantity_on_hand[^}]*\}/);
    expect(code).not.toMatch(/disabled=\{[^}]*quantity_reserved[^}]*\}/);
    expect(code).not.toMatch(/disabled=\{[^}]*available[^}]*\}/);
    expect(code).not.toMatch(/disabled=\{[^}]*compliance[^}]*\}/);
    expect(code).not.toMatch(
      /canSubmit[\s\S]{0,600}(quantity_on_hand|quantity_reserved|available|compliance_status)/,
    );
  });

  it("does NOT use optimistic updates or direct query cache mutation", async () => {
    const code = await readRuntimeSource("CreateOrderPage.tsx");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/invalidateQueries\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
    expect(code).not.toMatch(/\boptimistic\b/i);
  });
});
