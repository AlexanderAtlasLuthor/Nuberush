// F2.22.5.E: tests for the realtime invalidation bridge.
//
// The bridge MUST:
//   - call both subscription hooks (orders + inventory_items)
//   - render nothing (null)
//   - own no DOM / no state / no payload reading

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const useOrdersMock = vi.fn();
const useInventoryMock = vi.fn();

vi.mock("../useOrdersRealtimeSubscription", () => ({
  useOrdersRealtimeSubscription: () => useOrdersMock(),
}));

vi.mock("../useInventoryRealtimeSubscription", () => ({
  useInventoryRealtimeSubscription: () => useInventoryMock(),
}));

import { RealtimeInvalidationBridge } from "../RealtimeInvalidationBridge";

beforeEach(() => {
  useOrdersMock.mockReset();
  useInventoryMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("RealtimeInvalidationBridge", () => {
  it("calls both subscription hooks exactly once on mount", () => {
    render(<RealtimeInvalidationBridge />);
    expect(useOrdersMock).toHaveBeenCalledTimes(1);
    expect(useInventoryMock).toHaveBeenCalledTimes(1);
  });

  it("renders nothing (zero DOM nodes)", () => {
    const { container } = render(<RealtimeInvalidationBridge />);
    expect(container.firstChild).toBeNull();
  });
});
