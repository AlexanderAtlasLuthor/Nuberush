// F2.2: API client configuration.
//
// Single place that resolves the FastAPI backend base URL from Vite's
// build-time env vars. The fallback is a local-dev convenience; staging
// and production builds MUST set VITE_API_BASE_URL explicitly.
//
// No network calls happen here. This module is pure data.

const FALLBACK_BASE_URL = "http://localhost:8000";

const raw =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  FALLBACK_BASE_URL;

// Normalise: strip trailing slashes so callers can append paths starting
// with "/" without producing "//".
export const API_BASE_URL = raw.replace(/\/+$/, "");
