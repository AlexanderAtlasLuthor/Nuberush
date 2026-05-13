// F2.19.5 / Phase C: presentational KPI card.
//
// Renders a single backend-computed metric. Pure presentation — no
// data fetching, no context, no aggregation. The `value` and `title`
// are passed in by the parent (`KpiGrid`); this component never
// invents a default value (no `?? 0` fallback, no fake placeholder
// number).
//
// `to` makes the card a drill-down link when provided. The whole
// card body is wrapped in `<Link>` so the entire surface is the
// click target (matches the F2.18 admin pages' navigation pattern).
//
// Phase C — bento variants:
//   - "satellite" (default): compact card with eyebrow + value + muted
//     description, used for the 5 secondary KPIs.
//   - "hero": larger card with prominent value display, used for the
//     single operationally important KPI (Open orders today).
// Both variants source values verbatim from the backend payload —
// the variant only controls visual hierarchy, not data shape.

import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

export type KpiCardVariant = "hero" | "satellite";

export interface KpiCardProps {
  /** Short headline label for the metric (e.g. "Total stores"). */
  title: string;
  /** Backend value. Numbers are rendered verbatim — zero is a real
   * value and is NOT rendered as "—" or empty. */
  value: number;
  /** Optional one-line subhead under the value. */
  description?: string;
  /**
   * Optional drill-down route. When provided, the whole card becomes
   * a link to that path. The destination is opaque to this
   * component — the caller is responsible for the URL.
   */
  to?: string;
  /** Visual emphasis. Defaults to "satellite". */
  variant?: KpiCardVariant;
  /** Optional decorative icon shown in the card eyebrow. */
  icon?: LucideIcon;
  /** Optional test id for direct selection in tests. */
  "data-testid"?: string;
}

function KpiBody({
  title,
  value,
  description,
  variant = "satellite",
  icon: Icon,
}: KpiCardProps) {
  const isHero = variant === "hero";
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-2",
        isHero ? "p-5 md:p-6 md:gap-3" : "p-4 md:p-5",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p
          className={cn(
            "font-semibold uppercase tracking-wider text-muted-foreground truncate",
            isHero ? "text-[11px]" : "text-[10px]",
          )}
        >
          {title}
        </p>
        {Icon ? (
          <span
            className={cn(
              "inline-flex items-center justify-center rounded-md shrink-0",
              isHero
                ? "h-8 w-8 bg-primary/15 text-primary"
                : "h-7 w-7 bg-secondary/60 text-muted-foreground",
            )}
            aria-hidden="true"
          >
            <Icon className={isHero ? "h-4 w-4" : "h-3.5 w-3.5"} />
          </span>
        ) : null}
      </div>
      <p
        className={cn(
          "font-semibold tabular-nums tracking-tight leading-none",
          isHero
            ? "text-4xl md:text-5xl mt-1"
            : "text-2xl md:text-3xl",
        )}
      >
        {value}
      </p>
      {description ? (
        <p
          className={cn(
            "text-muted-foreground leading-snug",
            isHero ? "text-sm" : "text-xs",
          )}
        >
          {description}
        </p>
      ) : null}
    </div>
  );
}

export function KpiCard(props: KpiCardProps) {
  const { to, "data-testid": testId, variant = "satellite" } = props;
  const isHero = variant === "hero";

  const cardClassName = cn(
    "relative h-full rounded-xl border border-border bg-card transition-colors",
    isHero ? "shadow-sm" : "",
  );

  if (to) {
    return (
      <Link
        to={to}
        className={cn(
          cardClassName,
          "block hover:bg-secondary/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
        data-testid={testId}
      >
        <KpiBody {...props} />
      </Link>
    );
  }

  return (
    <div className={cardClassName} data-testid={testId}>
      <KpiBody {...props} />
    </div>
  );
}
