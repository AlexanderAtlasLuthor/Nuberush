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
//
// `accent` carries semantic intent (primary/success/warning/destructive/
// neutral) into surface tinting so the bento reads at a glance: green
// for healthy counts, amber for "watch", red for problems, orange for
// brand/action. Tailwind JIT needs literal class names, so the per-
// accent classes live in a static map below — do not template them.

import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

export type KpiCardVariant = "hero" | "satellite";
export type KpiAccent =
  | "primary"
  | "success"
  | "warning"
  | "destructive"
  | "neutral";

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
  /** Semantic surface tint. Defaults to "neutral". */
  accent?: KpiAccent;
  /** Optional test id for direct selection in tests. */
  "data-testid"?: string;
}

interface AccentTheme {
  satelliteSurface: string;
  satelliteIconChip: string;
  satelliteEyebrow: string;
  satelliteHover: string;
  heroSurface: string;
  heroIconChip: string;
  heroEyebrow: string;
  heroValue: string;
  heroDecoration: string;
  heroHover: string;
  focusRing: string;
}

const accentTheme: Record<KpiAccent, AccentTheme> = {
  neutral: {
    satelliteSurface: "border-border bg-card",
    satelliteIconChip: "bg-secondary/60 text-muted-foreground",
    satelliteEyebrow: "text-muted-foreground",
    satelliteHover: "hover:bg-secondary/40",
    heroSurface: "border-border bg-card shadow-sm",
    heroIconChip: "bg-primary/15 text-primary",
    heroEyebrow: "text-muted-foreground",
    heroValue: "",
    heroDecoration: "bg-primary/10",
    heroHover: "hover:bg-secondary/40",
    focusRing: "focus-visible:ring-ring",
  },
  primary: {
    satelliteSurface:
      "border-primary/25 bg-gradient-to-br from-primary/10 via-primary/[0.04] to-card",
    satelliteIconChip: "bg-primary/15 text-primary",
    satelliteEyebrow: "text-primary/90",
    satelliteHover: "hover:from-primary/15 hover:via-primary/[0.07]",
    heroSurface:
      "border-primary/30 bg-gradient-to-br from-primary/15 via-primary/5 to-card shadow-[0_0_0_1px_hsl(var(--primary)/0.08),0_20px_60px_-30px_hsl(var(--primary)/0.45)]",
    heroIconChip: "bg-primary/15 text-primary",
    heroEyebrow: "text-primary/90",
    heroValue: "text-primary",
    heroDecoration: "bg-primary/15",
    heroHover: "hover:from-primary/20 hover:via-primary/10",
    focusRing: "focus-visible:ring-primary",
  },
  success: {
    satelliteSurface:
      "border-success/25 bg-gradient-to-br from-success/10 via-success/[0.04] to-card",
    satelliteIconChip: "bg-success/15 text-success",
    satelliteEyebrow: "text-success/90",
    satelliteHover: "hover:from-success/15 hover:via-success/[0.07]",
    heroSurface:
      "border-success/30 bg-gradient-to-br from-success/15 via-success/5 to-card shadow-[0_0_0_1px_hsl(var(--success)/0.08),0_20px_60px_-30px_hsl(var(--success)/0.45)]",
    heroIconChip: "bg-success/15 text-success",
    heroEyebrow: "text-success/90",
    heroValue: "text-success",
    heroDecoration: "bg-success/15",
    heroHover: "hover:from-success/20 hover:via-success/10",
    focusRing: "focus-visible:ring-success",
  },
  warning: {
    satelliteSurface:
      "border-warning/25 bg-gradient-to-br from-warning/10 via-warning/[0.04] to-card",
    satelliteIconChip: "bg-warning/15 text-warning",
    satelliteEyebrow: "text-warning/90",
    satelliteHover: "hover:from-warning/15 hover:via-warning/[0.07]",
    heroSurface:
      "border-warning/30 bg-gradient-to-br from-warning/15 via-warning/5 to-card shadow-[0_0_0_1px_hsl(var(--warning)/0.08),0_20px_60px_-30px_hsl(var(--warning)/0.45)]",
    heroIconChip: "bg-warning/15 text-warning",
    heroEyebrow: "text-warning/90",
    heroValue: "text-warning",
    heroDecoration: "bg-warning/15",
    heroHover: "hover:from-warning/20 hover:via-warning/10",
    focusRing: "focus-visible:ring-warning",
  },
  destructive: {
    satelliteSurface:
      "border-destructive/25 bg-gradient-to-br from-destructive/10 via-destructive/[0.04] to-card",
    satelliteIconChip: "bg-destructive/15 text-destructive",
    satelliteEyebrow: "text-destructive/90",
    satelliteHover: "hover:from-destructive/15 hover:via-destructive/[0.07]",
    heroSurface:
      "border-destructive/30 bg-gradient-to-br from-destructive/15 via-destructive/5 to-card shadow-[0_0_0_1px_hsl(var(--destructive)/0.08),0_20px_60px_-30px_hsl(var(--destructive)/0.45)]",
    heroIconChip: "bg-destructive/15 text-destructive",
    heroEyebrow: "text-destructive/90",
    heroValue: "text-destructive",
    heroDecoration: "bg-destructive/15",
    heroHover: "hover:from-destructive/20 hover:via-destructive/10",
    focusRing: "focus-visible:ring-destructive",
  },
};

function KpiBody({
  title,
  value,
  description,
  variant = "satellite",
  icon: Icon,
  accent = "neutral",
}: KpiCardProps) {
  const isHero = variant === "hero";
  const theme = accentTheme[accent];
  return (
    <div
      className={cn(
        "relative flex h-full flex-col gap-2",
        isHero ? "p-5 md:p-6 md:gap-3" : "p-4 md:p-5",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p
          className={cn(
            "font-semibold uppercase tracking-wider truncate",
            isHero ? "text-[11px]" : "text-[10px]",
            isHero ? theme.heroEyebrow : theme.satelliteEyebrow,
          )}
        >
          {title}
        </p>
        {Icon ? (
          <span
            className={cn(
              "inline-flex items-center justify-center rounded-md shrink-0",
              isHero ? "h-8 w-8" : "h-7 w-7",
              isHero ? theme.heroIconChip : theme.satelliteIconChip,
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
          isHero ? "text-4xl md:text-5xl mt-1" : "text-2xl md:text-3xl",
          isHero ? theme.heroValue : "",
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
  const {
    to,
    "data-testid": testId,
    variant = "satellite",
    accent = "neutral",
  } = props;
  const isHero = variant === "hero";
  const theme = accentTheme[accent];

  const cardClassName = cn(
    "relative h-full overflow-hidden border transition-colors",
    isHero ? "rounded-2xl" : "rounded-xl",
    isHero ? theme.heroSurface : theme.satelliteSurface,
  );

  // Decorative corner glow only when there's an accent to celebrate —
  // a neutral satellite shouldn't carry decorative chrome.
  const decoration =
    isHero && accent !== "neutral" ? (
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl",
          theme.heroDecoration,
        )}
      />
    ) : null;

  if (to) {
    return (
      <Link
        to={to}
        className={cn(
          cardClassName,
          "block focus:outline-none focus-visible:ring-2",
          theme.focusRing,
          isHero ? theme.heroHover : theme.satelliteHover,
        )}
        data-testid={testId}
      >
        {decoration}
        <KpiBody {...props} />
      </Link>
    );
  }

  return (
    <div className={cardClassName} data-testid={testId}>
      {decoration}
      <KpiBody {...props} />
    </div>
  );
}
