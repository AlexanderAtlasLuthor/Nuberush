// F2.23.F1: API base URL resolution.
//
// `resolveApiBaseUrl` is the pure core of config.ts. Testing it directly
// (rather than stubbing import.meta.env + re-importing the module) keeps
// the dev fallback / production fail-fast / normalization rules verifiable
// without Vite/Vitest module-reset gymnastics.

import { describe, expect, it, vi } from "vitest";

import { resolveApiBaseUrl } from "./config";

describe("resolveApiBaseUrl", () => {
  it("falls back to http://localhost:8000 in development when env is missing", () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl(null, false)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl("", false)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl("   ", false)).toBe("http://localhost:8000");
  });

  it("uses the provided value in production", () => {
    expect(resolveApiBaseUrl("https://api.nuberush.example", true)).toBe(
      "https://api.nuberush.example",
    );
  });

  it("falls back (with a warning) in production when env is missing or blank", () => {
    // It must NOT throw — throwing crashed the whole app at module load
    // (blank screen). It warns and falls back instead.
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(resolveApiBaseUrl(undefined, true)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl(null, true)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl("", true)).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl("   ", true)).toBe("http://localhost:8000");
    expect(warn).toHaveBeenCalled();

    warn.mockRestore();
  });

  it("strips trailing slashes from a configured base URL", () => {
    expect(resolveApiBaseUrl("https://api.nuberush.example/", true)).toBe(
      "https://api.nuberush.example",
    );
    expect(resolveApiBaseUrl("https://api.nuberush.example///", false)).toBe(
      "https://api.nuberush.example",
    );
    expect(resolveApiBaseUrl("  https://api.nuberush.example/  ", true)).toBe(
      "https://api.nuberush.example",
    );
  });
});
