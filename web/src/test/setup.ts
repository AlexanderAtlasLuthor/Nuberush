import "@testing-library/jest-dom";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// JSDOM does not implement ResizeObserver; Radix UI primitives (Select,
// Popover, Tooltip, etc.) call it when measuring trigger geometry. Tests
// that mount any Radix Select-based modal would otherwise crash with
// "ReferenceError: ResizeObserver is not defined".
class ResizeObserverPolyfill {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== "undefined" && !("ResizeObserver" in window)) {
  Object.defineProperty(window, "ResizeObserver", {
    writable: true,
    value: ResizeObserverPolyfill,
  });
}
