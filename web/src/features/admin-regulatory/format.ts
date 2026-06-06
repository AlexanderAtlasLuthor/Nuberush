// F2.26.6.C: tiny presentation helpers shared by the regulatory read surface
// (desktop table + mobile cards). No business logic — formatting only.

/** Placeholder for missing optional fields (product_id, notice_id, resolved_at). */
export const EM_DASH = "—";

/**
 * Format an ISO timestamp as `YYYY-MM-DD HH:MM:SSZ`. Mirrors the inline
 * `formatTimestamp` used across the admin tables (no date library). Returns
 * the EM_DASH placeholder for null, and echoes the raw input if unparseable.
 */
export function formatTimestamp(iso: string | null): string {
  if (iso === null) return EM_DASH;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

/** Show an id verbatim, or the placeholder when null. */
export function idOrDash(value: string | null): string {
  return value === null ? EM_DASH : value;
}
