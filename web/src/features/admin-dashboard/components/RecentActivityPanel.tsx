// F2.19.5: recent activity panel.
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

import { Link } from "react-router-dom";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { AdminDashboardSummary } from "../types";

export interface RecentActivityPanelProps {
  events: AdminDashboardSummary["recent_audit"];
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export function RecentActivityPanel({ events }: RecentActivityPanelProps) {
  return (
    <Card data-testid="admin-dashboard-recent-activity">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold">
          Recent activity
        </CardTitle>
        <Link
          to="/app/admin/audit"
          className="text-sm text-muted-foreground hover:text-foreground"
          data-testid="recent-activity-view-all"
        >
          View all
        </Link>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="recent-activity-empty"
          >
            No recent activity yet.
          </p>
        ) : (
          <ul className="divide-y" data-testid="recent-activity-list">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex flex-col gap-1 py-2 text-sm"
                data-testid={`recent-activity-${event.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className="text-xs uppercase tracking-wide text-muted-foreground"
                    data-testid={`recent-activity-source-${event.id}`}
                  >
                    {event.source} · {event.entity_type}
                  </span>
                  <span
                    className="text-xs text-muted-foreground"
                    data-testid={`recent-activity-created-at-${event.id}`}
                  >
                    {formatTimestamp(event.created_at)}
                  </span>
                </div>
                <p
                  className="font-medium"
                  data-testid={`recent-activity-action-${event.id}`}
                >
                  {event.action}
                </p>
                <p
                  className="text-muted-foreground"
                  data-testid={`recent-activity-summary-${event.id}`}
                >
                  {event.summary}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
