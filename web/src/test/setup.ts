import "@testing-library/jest-dom";
import { vi } from "vitest";

// F2.22.2.G: `src/lib/supabase.ts` throws at import time when the
// Supabase env vars are missing. Provide harmless test values so any
// module that transitively imports the Supabase client (the whole
// `@/api` graph does) can load. `createClient` does no network I/O at
// construction; auth tests still mock `@/lib/supabase` to control
// session behaviour.
vi.stubEnv("VITE_SUPABASE_URL", "http://localhost:54321");
vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-anon-key");

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
