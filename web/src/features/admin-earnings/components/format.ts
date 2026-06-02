// F2.24.X5: USD formatting helper extracted from MoneyTile so the
// component file exports only components (Fast Refresh requirement).
// Accepts a string so USD `Decimal` amounts arriving from the wire stay
// precise until the final format step.

export function formatUsd(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}
