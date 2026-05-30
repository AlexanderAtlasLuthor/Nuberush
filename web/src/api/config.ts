// F2.2: API client configuration.
//
// Single place that resolves the FastAPI backend base URL from Vite's
// build-time env vars.
//
// Dev / non-production: a missing VITE_API_BASE_URL falls back to
// http://localhost:8000 as a local-dev convenience.
//
// Production (F2.23.F1): a missing or blank VITE_API_BASE_URL is a hard
// error. A production Cloudflare Pages build must never silently ship
// localhost API calls to users.
//
// No network calls happen here. This module is pure data.

const FALLBACK_BASE_URL = "http://localhost:8000";

/**
 * Resolve the API base URL from the raw env value.
 *
 * Blank values (undefined, null, "", whitespace-only) are treated as
 * missing. In production a missing value throws so the build cannot
 * silently fall back to localhost; outside production it falls back to the
 * local-dev default. Trailing slashes are stripped so callers can append
 * paths starting with "/" without producing "//".
 */
export function resolveApiBaseUrl(
  raw: string | undefined | null,
  isProduction: boolean,
): string {
  const trimmed = raw?.trim() ?? "";

  if (trimmed === "") {
    if (isProduction) {
      throw new Error("VITE_API_BASE_URL is required for production builds.");
    }
    return FALLBACK_BASE_URL;
  }

  return trimmed.replace(/\/+$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.PROD,
);
