// F2.2: focused unit tests for the API client foundation.
//
// Scope is intentionally narrow — error model + token holder. These two
// have no I/O and no React tree, so the tests are fast and deterministic.
// Network behaviour of `apiRequest` (fetch wiring, JSON parsing branches,
// error-shape normalisation) is NOT covered here: it requires either
// mocking the global fetch or hitting a real server, both of which add
// surface this scaffolding subphase shouldn't take on. Those tests will
// land alongside the first feature hook in a later subphase.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ApiError, getApiErrorMessage, isApiError } from "./errors";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./session-token";

describe("ApiError", () => {
  it("preserves status, message, details and code", () => {
    const err = new ApiError({
      status: 422,
      message: "Insufficient stock.",
      details: { detail: "Insufficient stock." },
      code: "stock_insufficient",
    });
    expect(err.status).toBe(422);
    expect(err.message).toBe("Insufficient stock.");
    expect(err.details).toEqual({ detail: "Insufficient stock." });
    expect(err.code).toBe("stock_insufficient");
    expect(err.name).toBe("ApiError");
  });

  it("is an instance of Error and ApiError", () => {
    const err = new ApiError({ status: 500, message: "boom" });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
  });

  it("does not require optional fields", () => {
    const err = new ApiError({ status: 0, message: "Network error" });
    expect(err.status).toBe(0);
    expect(err.details).toBeUndefined();
    expect(err.code).toBeUndefined();
  });
});

describe("isApiError", () => {
  it("returns true for an ApiError instance", () => {
    expect(
      isApiError(new ApiError({ status: 404, message: "not found" })),
    ).toBe(true);
  });

  it("returns false for a vanilla Error", () => {
    expect(isApiError(new Error("nope"))).toBe(false);
  });

  it("returns false for non-error values", () => {
    expect(isApiError("string")).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError({ status: 500, message: "duck-typed" })).toBe(false);
  });
});

describe("getApiErrorMessage", () => {
  it("extracts message from ApiError", () => {
    expect(
      getApiErrorMessage(
        new ApiError({ status: 422, message: "Invalid transition." }),
      ),
    ).toBe("Invalid transition.");
  });

  it("extracts message from vanilla Error", () => {
    expect(getApiErrorMessage(new Error("x"))).toBe("x");
  });

  it("returns the input when given a string", () => {
    expect(getApiErrorMessage("plain string")).toBe("plain string");
  });

  it("falls back to 'Unknown error' for unknown values", () => {
    expect(getApiErrorMessage(undefined)).toBe("Unknown error");
    expect(getApiErrorMessage(null)).toBe("Unknown error");
    expect(getApiErrorMessage({ random: "object" })).toBe("Unknown error");
    expect(getApiErrorMessage(42)).toBe("Unknown error");
  });
});

describe("session-token (memory holder)", () => {
  // Reset between tests so order does not matter.
  beforeEach(() => clearAccessToken());
  afterEach(() => clearAccessToken());

  it("starts as null", () => {
    expect(getAccessToken()).toBeNull();
  });

  it("set then get returns the token", () => {
    setAccessToken("abc.def.ghi");
    expect(getAccessToken()).toBe("abc.def.ghi");
  });

  it("setting null clears the token", () => {
    setAccessToken("abc.def.ghi");
    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
  });

  it("clearAccessToken() empties the holder", () => {
    setAccessToken("abc.def.ghi");
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });
});
