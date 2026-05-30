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
      // F2.23.F1 originally threw here. That crashed the entire app at
      // module load (blank screen) whenever VITE_API_BASE_URL was unset —
      // including the public marketing/legal pages that never call the
      // API. Until FastAPI has a hosted HTTPS origin to point at, warn
      // loudly but keep the app rendering. Re-tighten to a hard error once
      // the backend origin exists and is always set in production.
      console.warn(
        "VITE_API_BASE_URL is not set in this production build; falling " +
          "back to the local dev origin. Business API calls will fail " +
          "until it is configured.",
      );
    }
    return FALLBACK_BASE_URL;
  }

  return trimmed.replace(/\/+$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.PROD,
);
