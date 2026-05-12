// F2.19.5: presentational KPI card.
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

import { Link } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
  /** Optional test id for direct selection in tests. */
  "data-testid"?: string;
}

function KpiBody({ title, value, description }: KpiCardProps) {
  return (
    <>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {description ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {description}
          </p>
        ) : null}
      </CardContent>
    </>
  );
}

export function KpiCard(props: KpiCardProps) {
  const { to, "data-testid": testId } = props;

  if (to) {
    return (
      <Link
        to={to}
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
        data-testid={testId}
      >
        <Card className="transition-colors hover:bg-accent hover:text-accent-foreground">
          <KpiBody {...props} />
        </Card>
      </Link>
    );
  }

  return (
    <Card data-testid={testId}>
      <KpiBody {...props} />
    </Card>
  );
}
