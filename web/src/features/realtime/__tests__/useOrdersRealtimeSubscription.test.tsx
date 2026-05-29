// F2.22.5.D: tests for useOrdersRealtimeSubscription.
//
// The hook MUST: subscribe to `postgres_changes` on `public.orders`,
// invalidate `ordersKeys.all` on event, debounce bursts into one
// invalidation, and remove the channel on unmount. The payload is
// opaque — the hook MUST NOT call `setQueryData` and MUST NOT read
// the payload object.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

// ---- Supabase mock ---------------------------------------------------- //
// Captures every `.on(...)` registration and exposes a way to fire
// fake events at the registered callback. Tracks `.subscribe()` and
// `removeChannel` calls for the cleanup assertion.

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

import { useOrdersRealtimeSubscription } from "../useOrdersRealtimeSubscription";
import { ordersKeys } from "@/features/orders/hooks";

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

describe("useOrdersRealtimeSubscription — registration", () => {
  it("opens one channel and registers postgres_changes on public.orders", () => {
    renderHook(() => useOrdersRealtimeSubscription(), {
      wrapper: makeWrapper(makeClient()),
    });

    expect(channelMock).toHaveBeenCalledTimes(1);
    expect(channelMock).toHaveBeenCalledWith("realtime:orders");

    expect(onMock).toHaveBeenCalledTimes(1);
    const [event, filter] = onMock.mock.calls[0];
    expect(event).toBe("postgres_changes");
    expect(filter).toEqual({
      event: "*",
      schema: "public",
      table: "orders",
    });

    expect(subscribeMock).toHaveBeenCalledTimes(1);
  });
});

describe("useOrdersRealtimeSubscription — invalidation", () => {
  it("invalidates ordersKeys.all when a postgres_changes event arrives", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    renderHook(() => useOrdersRealtimeSubscription({ debounceMs: 100 }), {
      wrapper: makeWrapper(client),
    });

    expect(registered).toHaveLength(1);
    // Fire a fake event — payload is intentionally a real-looking
    // object to confirm the hook does NOT use it.
    registered[0].cb({
      eventType: "UPDATE",
      schema: "public",
      table: "orders",
      new: { id: "should-not-be-read", store_id: "x" },
      old: {},
    });

    // Before debounce expires: no invalidation yet.
    expect(invalidateSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);

    expect(invalidateSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ordersKeys.all,
    });
  });

  it("coalesces a burst of events into a single invalidation", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    renderHook(() => useOrdersRealtimeSubscription({ debounceMs: 100 }), {
      wrapper: makeWrapper(client),
    });

    // 5 events in rapid succession.
    for (let i = 0; i < 5; i++) {
      registered[0].cb({ eventType: "INSERT", table: "orders" });
    }
    vi.advanceTimersByTime(50);
    // Still inside the debounce window — more events.
    for (let i = 0; i < 3; i++) {
      registered[0].cb({ eventType: "UPDATE", table: "orders" });
    }

    expect(invalidateSpy).not.toHaveBeenCalled();
    vi.advanceTimersByTime(50);
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
  });

  it("opens a fresh debounce window after the first invalidation fires", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    renderHook(() => useOrdersRealtimeSubscription({ debounceMs: 100 }), {
      wrapper: makeWrapper(client),
    });

    registered[0].cb({ eventType: "UPDATE", table: "orders" });
    vi.advanceTimersByTime(100);
    expect(invalidateSpy).toHaveBeenCalledTimes(1);

    registered[0].cb({ eventType: "UPDATE", table: "orders" });
    vi.advanceTimersByTime(100);
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

describe("useOrdersRealtimeSubscription — cleanup", () => {
  it("removes the channel on unmount", () => {
    const { unmount } = renderHook(() => useOrdersRealtimeSubscription(), {
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
      () => useOrdersRealtimeSubscription({ debounceMs: 200 }),
      { wrapper: makeWrapper(client) },
    );

    // Fire an event but unmount before the timer can fire.
    registered[0].cb({ eventType: "INSERT", table: "orders" });
    unmount();
    vi.advanceTimersByTime(500);

    // No invalidation should have fired post-unmount.
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

describe("useOrdersRealtimeSubscription — payload boundary", () => {
  it("does not call setQueryData with the event payload", () => {
    vi.useFakeTimers();
    const client = makeClient();
    const setQueryDataSpy = vi.spyOn(client, "setQueryData");

    renderHook(() => useOrdersRealtimeSubscription({ debounceMs: 50 }), {
      wrapper: makeWrapper(client),
    });

    registered[0].cb({
      eventType: "UPDATE",
      table: "orders",
      new: { id: "leak-canary", store_id: "x", total_amount: "999.99" },
      old: { id: "leak-canary" },
    });
    vi.advanceTimersByTime(50);

    expect(setQueryDataSpy).not.toHaveBeenCalled();
  });
});
