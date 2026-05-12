// F2.7.0 subfase 4: orders mutations tests.
//
// Two-test pattern per mutation:
//   1. mutationFn receives the variables verbatim (api function called
//      with exactly the params the caller passed to mutate()).
//   2. onSuccess invalidates EXACTLY the four expected scopes — broad
//      orders list, specific order item, specific order audit-logs,
//      and the cross-feature inventory list. `toHaveBeenCalledTimes(4)`
//      acts as a regression guard against extra/missed invalidations.
//
// `inventoryKeys` is imported real (not mocked) — it's a pure data
// factory and mocking it would defeat the cross-feature contract test.
// Same for `ordersKeys`.

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCreateOrderMutation } from "../useCreateOrderMutation";
import { useTransitionOrderStatusMutation } from "../useTransitionOrderStatusMutation";
import { useCancelOrderMutation } from "../useCancelOrderMutation";
import { useReturnOrderMutation } from "../useReturnOrderMutation";
import { ordersKeys } from "../queryKeys";
import { inventoryKeys } from "@/features/inventory/hooks";
import * as ordersApi from "../../api";

vi.mock("../../api", () => ({
  getOrdersList: vi.fn(),
  getOrder: vi.fn(),
  getOrderAuditLogs: vi.fn(),
  createOrder: vi.fn(),
  transitionOrderStatus: vi.fn(),
  cancelOrder: vi.fn(),
  returnOrder: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ORDER_ID = "22222222-2222-2222-2222-222222222222";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function expectStandardInvalidations(
  spy: MockInstance,
  orderId: string,
) {
  expect(spy).toHaveBeenCalledWith({ queryKey: ordersKeys.lists() });
  expect(spy).toHaveBeenCalledWith({
    queryKey: ordersKeys.item(orderId),
  });
  expect(spy).toHaveBeenCalledWith({
    queryKey: ordersKeys.auditLogs(orderId),
  });
  // 🔥 Cross-feature: the contract every orders mutation must honour.
  expect(spy).toHaveBeenCalledWith({ queryKey: inventoryKeys.lists() });
  expect(spy).toHaveBeenCalledTimes(4);
}

beforeEach(() => {
  vi.mocked(ordersApi.createOrder).mockReset();
  vi.mocked(ordersApi.transitionOrderStatus).mockReset();
  vi.mocked(ordersApi.cancelOrder).mockReset();
  vi.mocked(ordersApi.returnOrder).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useCreateOrderMutation
// --------------------------------------------------------------------- //

describe("useCreateOrderMutation", () => {
  it("calls createOrder with the variables passed to mutate()", async () => {
    vi.mocked(ordersApi.createOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    const variables = {
      storeId: STORE_ID,
      body: {
        idempotency_key: "key-abc",
        items: [{ variant_id: "v-1", quantity: 3 }],
      },
    };
    result.current.mutate(variables);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.createOrder).toHaveBeenCalledTimes(1);
    expect(ordersApi.createOrder).toHaveBeenCalledWith(variables);
  });

  it("invalidates orders.lists, orders.item(data.id), orders.auditLogs(data.id) and inventory.lists on success", async () => {
    // The new order's id comes from the response (server-generated),
    // not from variables — so the test asserts invalidation against
    // `data.id`.
    vi.mocked(ordersApi.createOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      storeId: STORE_ID,
      body: {
        idempotency_key: "key-xyz",
        items: [{ variant_id: "v-1", quantity: 1 }],
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expectStandardInvalidations(invalidateSpy, ORDER_ID);
  });
});

// --------------------------------------------------------------------- //
// useTransitionOrderStatusMutation
// --------------------------------------------------------------------- //

describe("useTransitionOrderStatusMutation", () => {
  it("calls transitionOrderStatus with the variables passed to mutate()", async () => {
    vi.mocked(ordersApi.transitionOrderStatus).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useTransitionOrderStatusMutation(),
      { wrapper: makeWrapper(client) },
    );

    const variables = {
      orderId: ORDER_ID,
      body: { new_status: "preparing" as const },
    };
    result.current.mutate(variables);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.transitionOrderStatus).toHaveBeenCalledTimes(1);
    expect(ordersApi.transitionOrderStatus).toHaveBeenCalledWith(variables);
  });

  it("invalidates the four expected scopes on success", async () => {
    vi.mocked(ordersApi.transitionOrderStatus).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useTransitionOrderStatusMutation(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({
      orderId: ORDER_ID,
      body: { new_status: "ready" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expectStandardInvalidations(invalidateSpy, ORDER_ID);
  });
});

// --------------------------------------------------------------------- //
// useCancelOrderMutation
// --------------------------------------------------------------------- //

describe("useCancelOrderMutation", () => {
  it("calls cancelOrder with the variables passed to mutate()", async () => {
    vi.mocked(ordersApi.cancelOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCancelOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    const variables = {
      orderId: ORDER_ID,
      body: { reason: "customer changed mind" },
    };
    result.current.mutate(variables);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.cancelOrder).toHaveBeenCalledTimes(1);
    expect(ordersApi.cancelOrder).toHaveBeenCalledWith(variables);
  });

  it("invalidates the four expected scopes on success", async () => {
    vi.mocked(ordersApi.cancelOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCancelOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      orderId: ORDER_ID,
      body: { reason: "store closed" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expectStandardInvalidations(invalidateSpy, ORDER_ID);
  });
});

// --------------------------------------------------------------------- //
// useReturnOrderMutation
// --------------------------------------------------------------------- //

describe("useReturnOrderMutation", () => {
  it("calls returnOrder with the variables passed to mutate()", async () => {
    vi.mocked(ordersApi.returnOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useReturnOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    const variables = {
      orderId: ORDER_ID,
      body: { reason: "defective unit" },
    };
    result.current.mutate(variables);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.returnOrder).toHaveBeenCalledTimes(1);
    expect(ordersApi.returnOrder).toHaveBeenCalledWith(variables);
  });

  it("invalidates the four expected scopes on success", async () => {
    vi.mocked(ordersApi.returnOrder).mockResolvedValue({
      id: ORDER_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useReturnOrderMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      orderId: ORDER_ID,
      body: { reason: "warranty exchange" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expectStandardInvalidations(invalidateSpy, ORDER_ID);
  });
});
