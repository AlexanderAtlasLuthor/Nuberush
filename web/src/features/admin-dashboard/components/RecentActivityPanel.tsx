// F2.19.5 / Phase C: recent activity panel.
//
// Renders the backend-provided `recent_audit` tail (bounded to 5
// by the backend). Pure presentational — never fetches audit
// separately, never re-sorts, never merges audit sources (the
// backend's `list_admin_audit` aggregator already does that).
//
// Each row exposes the source/entity, action, summary and timestamp
// from the existing `AuditEvent` shape. No actor name lookup — the
// backend exposes `actor_id` (a UUID) and the dashboard surface
// renders it verbatim when present; richer enrichment belongs on
// the dedicated audit page.
//
// Phase C — visual upgrade adapted from the NubeRush Design System
// ZIP (`ActivityTimeline.jsx`):
//   - Vertical timeline with a colored dot per row mapped from the
//     real `event.source` value.
//   - Source chip rendered from the real `source` string.
//   - Rejected from the ZIP: pre-formatted "relative" time strings
//     (the wire only carries the ISO timestamp) and made-up audit
//     events / actor names.

import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

import type { AdminDashboardSummary } from "../types";

type AuditEvent = AdminDashboardSummary["recent_audit"][number];

// Visual mapping for the timeline dot. Unknown sources fall back to
// a neutral muted dot so future backend additions don't crash the
// UI — they simply render less prominently until they get a color.
const SOURCE_DOT_CLASS: Record<string, string> = {
  inventory: "bg-primary",
  order: "bg-warning",
  orders: "bg-warning",
  compliance: "bg-destructive",
  auth: "bg-success",
  stores: "bg-muted-foreground/80",
};

function dotClassFor(source: string): string {
  return SOURCE_DOT_CLASS[source] ?? "bg-muted-foreground/80";
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export interface RecentActivityPanelProps {
  events: AdminDashboardSummary["recent_audit"];
}

export function RecentActivityPanel({ events }: RecentActivityPanelProps) {
  return (
    <section
      className="rounded-xl border border-border bg-card flex flex-col"
      data-testid="admin-dashboard-recent-activity"
      aria-label="Recent activity"
    >
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4 md:px-6">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Recent activity</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Audit tail — bounded to 5 by the backend.
          </p>
        </div>
        <Link
          to="/app/admin/audit"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground shrink-0"
          data-testid="recent-activity-view-all"
        >
          View all
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      </header>
      <div className="px-5 md:px-6">
        {events.length === 0 ? (
          <p
            className="py-5 text-sm text-muted-foreground"
            data-testid="recent-activity-empty"
          >
            No recent activity yet.
          </p>
        ) : (
          <RenderTimeline events={events} />
        )}
      </div>
    </section>
  );
}

function RenderTimeline({ events }: { events: ReadonlyArray<AuditEvent> }) {
  return (
    <ol
      className="relative py-4"
      data-testid="recent-activity-list"
    >
      {/* Vertical guide line behind the dots. Decorative only. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-[7px] top-5 bottom-5 w-px bg-border"
      />
      {events.map((event) => (
        <li
          key={event.id}
          className="relative pl-7 pb-4 last:pb-0 text-sm"
          data-testid={`recent-activity-${event.id}`}
        >
          <span
            className={cn(
              "absolute left-0 top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-card",
              dotClassFor(event.source),
            )}
            aria-hidden="true"
          />
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span
              className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wider text-muted-foreground bg-secondary/60 rounded px-1.5 py-0.5"
              data-testid={`recent-activity-source-${event.id}`}
            >
              {event.source} · {event.entity_type}
            </span>
            <span
              className="text-[11px] text-muted-foreground tabular-nums"
              data-testid={`recent-activity-created-at-${event.id}`}
            >
              {formatTimestamp(event.created_at)}
            </span>
          </div>
          <p
            className="mt-1 font-medium"
            data-testid={`recent-activity-action-${event.id}`}
          >
            {event.action}
          </p>
          <p
            className="mt-0.5 text-xs text-muted-foreground leading-relaxed"
            data-testid={`recent-activity-summary-${event.id}`}
          >
            {event.summary}
          </p>
        </li>
      ))}
    </ol>
  );
}
