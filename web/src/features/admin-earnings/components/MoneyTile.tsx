// Small money-formatted tile used by the earnings views. Mirrors the
// visual language of `@/features/admin-dashboard/components/KpiCard`
// (eyebrow + big value + description) but accepts a string value so
// USD `Decimal` amounts arriving from the wire stay precise.

import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

import { formatUsd } from "./format";

export type MoneyTileVariant = "hero" | "satellite";

export interface MoneyTileProps {
  title: string;
  value: string;
  description?: string;
  to?: string;
  variant?: MoneyTileVariant;
  icon?: LucideIcon;
  "data-testid"?: string;
}


function TileBody({
  title,
  value,
  description,
  variant = "satellite",
  icon: Icon,
}: MoneyTileProps) {
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
          isHero ? "text-4xl md:text-5xl mt-1" : "text-2xl md:text-3xl",
        )}
      >
        {formatUsd(value)}
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

export function MoneyTile(props: MoneyTileProps) {
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
        <TileBody {...props} />
      </Link>
    );
  }

  return (
    <div className={cardClassName} data-testid={testId}>
      <TileBody {...props} />
    </div>
  );
}

