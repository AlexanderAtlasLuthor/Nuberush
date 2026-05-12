// F2.7.0 subfase 4: useOrderAuditLogs tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useOrderAuditLogs } from "../useOrderAuditLogs";
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
  vi.mocked(ordersApi.getOrderAuditLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useOrderAuditLogs", () => {
  it("fires the query and caches under ['orders','auditLogs', orderId] for a valid id", async () => {
    const fakeLogs = [{ id: "log-1" }] as unknown;
    vi.mocked(ordersApi.getOrderAuditLogs).mockResolvedValue(
      fakeLogs as never,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useOrderAuditLogs(ORDER_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.getOrderAuditLogs).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(ordersApi.getOrderAuditLogs).mock.calls[0];
    expect(args).toEqual({ orderId: ORDER_ID });

    const expectedKey = ordersKeys.auditLogs(ORDER_ID);
    expect(expectedKey).toEqual(["orders", "auditLogs", ORDER_ID]);
    expect(client.getQueryData(expectedKey)).toBe(fakeLogs);
  });

  it("does not fire the query when the id is empty", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useOrderAuditLogs(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(ordersApi.getOrderAuditLogs).not.toHaveBeenCalled();
  });
});
