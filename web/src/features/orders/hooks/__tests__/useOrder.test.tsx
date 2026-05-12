// F2.7.0 subfase 4: useOrder tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useOrder } from "../useOrder";
import { ordersKeys } from "../queryKeys";
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

const ORDER_ID = "22222222-2222-2222-2222-222222222222";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
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

beforeEach(() => {
  vi.mocked(ordersApi.getOrder).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useOrder", () => {
  it("fires the query and caches under ['orders','item', orderId] for a valid id", async () => {
    const fakeOrder = { id: ORDER_ID, store_id: "x" } as unknown;
    vi.mocked(ordersApi.getOrder).mockResolvedValue(fakeOrder as never);
    const client = makeQueryClient();

    const { result } = renderHook(() => useOrder(ORDER_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.getOrder).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(ordersApi.getOrder).mock.calls[0];
    expect(args).toEqual({ orderId: ORDER_ID });

    expect(client.getQueryData(ordersKeys.item(ORDER_ID))).toBe(fakeOrder);
  });

  it("does not fire the query when the id is empty", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useOrder(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(ordersApi.getOrder).not.toHaveBeenCalled();
  });
});
