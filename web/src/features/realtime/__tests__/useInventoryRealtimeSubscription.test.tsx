// F2.22.5.D: tests for useInventoryRealtimeSubscription.
//
// Same shape as the orders hook tests — see that file for the broader
// commentary. This file asserts the inventory variant binds to
// `public.inventory_items` and invalidates `inventoryKeys.all`.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const onMock = vi.fn();
const subscribeMock = vi.fn();
const removeChannelMock = vi.fn();
const channelMock = vi.fn();

interface RegisteredHandler {
  event: string;
  filter: { event: string; schema: string; table: string };
  cb: (payload: unknown) => void;
}
const registered: RegisteredHandler[] = [];

vi.mock("@/lib/supabase", () => {
  const channelObj = {
    on: (
      event: string,
      filter: { event: string; schema: string; table: string },
      cb: (payload: unknown) => void,
    ) => {
      registered.push({ event, filter, cb });
      onMock(event, filter, cb);
      return channelObj;
    },
    subscribe: () => {
      subscribeMock();
      return channelObj;
    },
  };
  return {
    supabase: {
      channel: (name: string) => {
        channelMock(name);
        return channelObj;
      },
      removeChannel: (channel: unknown) => {
        removeChannelMock(channel);
      },
    },
  };
});

import { useInventoryRealtimeSubscription } from "../useInventoryRealtimeSubscription";
import { inventoryKeys } from "@/features/inventory/hooks";

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

beforeEach(() => {
  onMock.mockReset();
  subscribeMock.mockReset();
  removeChannelMock.mockReset();
  channelMock.mockReset();
  registered.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("useInventoryRealtimeSubscription — registration", () => {
  it("opens one channel and registers postgres_changes on public.inventory_items", () => {
    renderHook(() => useInventoryRealtimeSubscription(), {
      wrapper: makeWrapper(makeClient()),
    });

    expect(channelMock).toHaveBeenCalledTimes(1);
    expect(channelMock).toHaveBeenCalledWith("realtime:inventory_items");

    expect(onMock).toHaveBeenCalledTimes(1);
    const [event, filter] = onMock.mock.calls[0];
    expect(event).toBe("postgres_changes");
    expect(filter).toEqual({
      event: "*",
      schema: "public",
      table: "inventory_items",
    });

    expect(subscribeMock).toHaveBeenCalledTimes(1);
  });
});

describe("useInventoryRealtimeSubscription — invalidation", () => {
  it("invalidates inventoryKeys.all when an event arrives", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    renderHook(
      () => useInventoryRealtimeSubscription({ debounceMs: 100 }),
      { wrapper: makeWrapper(client) },
    );

    registered[0].cb({
      eventType: "UPDATE",
      schema: "public",
      table: "inventory_items",
      new: { id: "should-not-be-read", quantity_on_hand: 0 },
      old: {},
    });
    expect(invalidateSpy).not.toHaveBeenCalled();
    vi.advanceTimersByTime(100);
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.all,
    });
  });

  it("coalesces a burst of events into a single invalidation", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    renderHook(
      () => useInventoryRealtimeSubscription({ debounceMs: 100 }),
      { wrapper: makeWrapper(client) },
    );

    for (let i = 0; i < 10; i++) {
      registered[0].cb({ eventType: "UPDATE", table: "inventory_items" });
    }
    vi.advanceTimersByTime(100);
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
  });
});

describe("useInventoryRealtimeSubscription — cleanup", () => {
  it("removes the channel on unmount", () => {
    const { unmount } = renderHook(() => useInventoryRealtimeSubscription(), {
      wrapper: makeWrapper(makeClient()),
    });
    expect(removeChannelMock).not.toHaveBeenCalled();
    unmount();
    expect(removeChannelMock).toHaveBeenCalledTimes(1);
  });

  it("clears the pending debounce timer on unmount", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { unmount } = renderHook(
      () => useInventoryRealtimeSubscription({ debounceMs: 200 }),
      { wrapper: makeWrapper(client) },
    );

    registered[0].cb({ eventType: "INSERT", table: "inventory_items" });
    unmount();
    vi.advanceTimersByTime(500);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

describe("useInventoryRealtimeSubscription — payload boundary", () => {
  it("does not call setQueryData with the event payload", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const setQueryDataSpy = vi.spyOn(client, "setQueryData");

    renderHook(
      () => useInventoryRealtimeSubscription({ debounceMs: 50 }),
      { wrapper: makeWrapper(client) },
    );

    registered[0].cb({
      eventType: "UPDATE",
      table: "inventory_items",
      new: { id: "leak-canary", store_id: "x", quantity_on_hand: 0 },
      old: { id: "leak-canary" },
    });
    vi.advanceTimersByTime(50);

    expect(setQueryDataSpy).not.toHaveBeenCalled();
  });
});
