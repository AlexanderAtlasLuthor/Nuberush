// Hero card for the "what you actually earn" metric — commission for
// admin, product revenue for store. Uses the success/emerald token
// for green money-feel, a large tabular-nums value, and an optional
// horizontal composition bar that shows how the gross customer
// payment breaks down (subtotal vs delivery vs tax vs commission).

import { DollarSign, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

import { formatUsd } from "./MoneyTile";

export interface CompositionSegment {
  label: string;
  amount: string;
  /**
   * Tailwind class for the segment background. Leave undefined for
   * the "your earnings" highlight segment — the component renders it
   * in the success token automatically.
   */
  colorClass?: string;
  highlight?: boolean;
}

export interface EarningsHeroCardProps {
  /** Small uppercase eyebrow. e.g. "Commission earned". */
  eyebrow: string;
  /** Money string (USD) from the wire. Formatted with Intl. */
  value: string;
  /** Below the value. e.g. "12 delivered orders". */
  description?: string;
  /** Icon shown in the chip. Defaults to DollarSign. */
  icon?: LucideIcon;
  /**
   * Optional composition bar. Segments render in order; the highlight
   * segment (or last segment if none flagged) uses the success token.
   * Pass `undefined` to hide the bar (e.g. the widget compact variant).
   */
  composition?: CompositionSegment[];
  /** Optional drill-down link. Wraps the whole card in <Link>. */
  to?: string;
  /** Compact = smaller padding and font sizes, for widget embeds. */
  compact?: boolean;
  "data-testid"?: string;
}

function parseAmount(amount: string): number {
  const parsed = Number(amount);
  return Number.isFinite(parsed) ? parsed : 0;
}

function CompositionBar({ segments }: { segments: CompositionSegment[] }) {
  const total = segments.reduce(
    (acc, segment) => acc + parseAmount(segment.amount),
    0,
  );
  if (total <= 0) return null;

  const fallbackPalette = [
    "bg-foreground/25",
    "bg-foreground/15",
    "bg-foreground/10",
  ];

  return (
    <div className="space-y-2.5">
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-foreground/5"
        role="img"
        aria-label="Earnings composition"
      >
        {segments.map((segment, index) => {
          const pct = (parseAmount(segment.amount) / total) * 100;
          if (pct <= 0) return null;
          const colorClass =
            segment.colorClass ??
            (segment.highlight
              ? "bg-success"
              : fallbackPalette[index % fallbackPalette.length]);
          return (
            <div
              key={segment.label}
              className={cn("h-full", colorClass)}
              style={{ width: `${pct}%` }}
            />
          );
        })}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] md:grid-cols-4">
        {segments.map((segment, index) => {
          const colorClass =
            segment.colorClass ??
            (segment.highlight
              ? "bg-success"
              : fallbackPalette[index % fallbackPalette.length]);
          return (
            <li
              key={segment.label}
              className="flex items-center gap-1.5 min-w-0"
            >
              <span
                className={cn("h-2 w-2 rounded-full shrink-0", colorClass)}
                aria-hidden="true"
              />
              <span className="truncate text-muted-foreground">
                {segment.label}
              </span>
              <span
                className={cn(
                  "ml-auto tabular-nums font-medium",
                  segment.highlight ? "text-success" : "text-foreground",
                )}
              >
                {formatUsd(segment.amount)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CardBody({
  eyebrow,
  value,
  description,
  icon: Icon = DollarSign,
  composition,
  compact = false,
}: EarningsHeroCardProps) {
  return (
    <div
      className={cn(
        "relative flex h-full flex-col gap-3",
        compact ? "p-5" : "p-6 md:p-7 md:gap-4",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p
          className={cn(
            "font-semibold uppercase tracking-wider text-success/90",
            compact ? "text-[10px]" : "text-[11px]",
          )}
        >
          {eyebrow}
        </p>
        <span
          className={cn(
            "inline-flex items-center justify-center rounded-lg bg-success/15 text-success shrink-0",
            compact ? "h-8 w-8" : "h-10 w-10",
          )}
          aria-hidden="true"
        >
          <Icon className={compact ? "h-4 w-4" : "h-5 w-5"} />
        </span>
      </div>

      <div className="flex flex-col gap-1.5">
        <p
          className={cn(
            "font-semibold tabular-nums tracking-tight leading-none text-success",
            compact
              ? "text-4xl md:text-[40px]"
              : "text-5xl md:text-6xl",
          )}
        >
          {formatUsd(value)}
        </p>
        {description ? (
          <p
            className={cn(
              "text-muted-foreground leading-snug",
              compact ? "text-xs" : "text-sm",
            )}
          >
            {description}
          </p>
        ) : null}
      </div>

      {composition && composition.length > 0 ? (
        <div className={cn("mt-auto", compact ? "pt-2" : "pt-3 md:pt-4")}>
          <CompositionBar segments={composition} />
        </div>
      ) : null}
    </div>
  );
}

export function EarningsHeroCard(props: EarningsHeroCardProps) {
  const { to, "data-testid": testId } = props;
  // Layered emerald glow: gradient + ring so the card visibly reads as
  // money/income without overpowering the surrounding neutral tiles.
  const cardClassName = cn(
    "relative overflow-hidden rounded-2xl border border-success/30",
    "bg-gradient-to-br from-success/15 via-success/5 to-card",
    "shadow-[0_0_0_1px_hsl(var(--success)/0.08),0_20px_60px_-30px_hsl(var(--success)/0.45)]",
    "transition-colors h-full",
  );

  const decoration = (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-success/15 blur-3xl"
    />
  );

  if (to) {
    return (
      <Link
        to={to}
        className={cn(
          cardClassName,
          "block hover:from-success/20 hover:via-success/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-success",
        )}
        data-testid={testId}
      >
        {decoration}
        <CardBody {...props} />
      </Link>
    );
  }

  return (
    <div className={cardClassName} data-testid={testId}>
      {decoration}
      <CardBody {...props} />
    </div>
  );
}
