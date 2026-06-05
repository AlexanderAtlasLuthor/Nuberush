// Shared pre-Stripe earnings disclaimer (F2.26.4.A).
//
// Stripe payment processing is not enabled yet, so every figure on the
// admin and store earnings surfaces is a projected internal-accounting
// estimate — not processed payment activity. This single component keeps
// the framing identical everywhere it appears and always states all
// three facts: (1) projected/internal accounting, (2) Stripe not yet
// enabled, (3) no funds charged or paid out through NubeRush yet.

import { Info } from "lucide-react";

interface EarningsDisclaimerProps {
  "data-testid"?: string;
}

export function EarningsDisclaimer({
  "data-testid": testId = "earnings-disclaimer",
}: EarningsDisclaimerProps) {
  return (
    <div
      role="note"
      data-testid={testId}
      className="flex items-start gap-2 rounded-lg border border-border bg-secondary/30 px-3 py-2 text-xs text-muted-foreground"
    >
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        Projected internal accounting. Stripe payment processing is not yet
        enabled, and no funds have been charged or paid out through NubeRush
        yet.
      </span>
    </div>
  );
}
