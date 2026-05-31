// F2.24.C7: shared timestamp formatting for the admin store-applications
// surfaces. Mirrors the lightweight, no-dependency approach used across
// the other admin features (e.g. features/stores) — locale date for
// lists, locale date-time for detail. Nullable wire fields render as an
// em dash so empty cells stay legible.

export function formatApplicationDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatApplicationDateTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}
