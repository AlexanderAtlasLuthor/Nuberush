// F2.16.5: presentational table for the unified store audit feed.
//
// Pure presentational component. Parent owns the data fetch (via
// `useStoreAuditQuery`) and forwards its result through the typed
// props. No hooks, no API calls, no derived business truth.
//
// Render states:
//   - isLoading                 →  LoadingState
//   - error (truthy)            →  ErrorState (+ Retry button if onRetry)
//   - events.length === 0       →  EmptyState
//   - otherwise                 →  Table with one row per event
//
// Columns (locked by F2.16 prompt):
//   Time | Source | Summary | Action | Entity | Actor
//
// Data mapping:
//   - Time:    `created_at` formatted via Intl.DateTimeFormat with a
//              short date + time. We use the runtime's default locale
//              and rely on the browser's TZ; no timezone gymnastics.
//   - Source:  rendered via `AuditEventBadge`.
//   - Summary: `event.summary` verbatim.
//   - Action:  `event.action` verbatim.
//   - Entity:  `entity_type` (uppercased label) + the short
//              `entity_id` (first 8 hex chars, mirroring how the
//              backend logs are typically referenced).
//   - Actor:   `event.actor_id` if present (short form), else
//              "System" — the backend writes `actor_id = null` for
//              system-originated rows.
//
// Forbidden:
//   - No useAuth / no useStore / no fetch / no hooks.
//   - No derived `actor_name`, `actor_email`, `store_name`,
//     `severity`, `source_label`, `entity_label` — those are not
//     on the wire.
//   - No fake rows.

import { History } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { AuditEntityType, AuditEvent } from "../types";
import { AuditEventBadge } from "./AuditEventBadge";

const ENTITY_LABEL: Record<AuditEntityType, string> = {
  inventory_item: "Inventory item",
  order: "Order",
  product: "Product",
};

const DATE_TIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function formatCreatedAt(value: string): string {
  // Fall back to the raw ISO string if parsing fails so the UI
  // never silently swallows malformed wire data.
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return DATE_TIME_FORMAT.format(parsed);
}

function shortId(value: string): string {
  // A short prefix is enough to identify the row in the operator's
  // UI; long UUIDs visually break table columns. The raw value is
  // exposed via the `title` attribute for hover/copy.
  return value.length > 8 ? value.slice(0, 8) : value;
}

export interface AuditFeedProps {
  events: AuditEvent[];
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /**
   * Card title (default: "Activity"). F2.18.4 added the override so
   * the same presentational component can render the store-scoped
   * feed and the admin global feed without the description lying
   * about scope.
   */
  title?: string;
  /**
   * Card description shown under the title. Defaults to the
   * store-scoped copy. F2.18.4 added the override for the admin
   * global feed, which spans every store.
   */
  description?: string;
  /**
   * Title shown when the feed is empty (default: "No audit events").
   */
  emptyTitle?: string;
  /**
   * Description shown when the feed is empty (default:
   * "No activity recorded for the selected filters.").
   */
  emptyDescription?: string;
  className?: string;
}

const SYSTEM_PLACEHOLDER = "System";
const DEFAULT_TITLE = "Activity";
const DEFAULT_DESCRIPTION =
  "Inventory, order, and compliance events for this store.";
const DEFAULT_EMPTY_TITLE = "No audit events";
const DEFAULT_EMPTY_DESCRIPTION =
  "No activity recorded for the selected filters.";

export function AuditFeed({
  events,
  isLoading = false,
  error,
  onRetry,
  title = DEFAULT_TITLE,
  description = DEFAULT_DESCRIPTION,
  emptyTitle = DEFAULT_EMPTY_TITLE,
  emptyDescription = DEFAULT_EMPTY_DESCRIPTION,
  className,
}: AuditFeedProps) {
  return (
    <Card className={className} data-testid="audit-feed">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <LoadingState message="Loading audit events…" />
        ) : error ? (
          <ErrorState
            title="Audit feed failed to load"
            message="The audit feed could not be loaded."
            onRetry={onRetry}
          />
        ) : events.length === 0 ? (
          <EmptyState
            icon={History}
            title={emptyTitle}
            message={emptyDescription}
          />
        ) : (
          <div
            className="rounded-b-md border-t border-border"
            data-testid="audit-feed-table-wrapper"
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Actor</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow
                    key={event.id}
                    data-testid={`audit-feed-row-${event.id}`}
                  >
                    <TableCell
                      className="whitespace-nowrap text-sm text-muted-foreground"
                      data-testid={`audit-feed-time-${event.id}`}
                      title={event.created_at}
                    >
                      {formatCreatedAt(event.created_at)}
                    </TableCell>
                    <TableCell
                      data-testid={`audit-feed-source-${event.id}`}
                    >
                      <AuditEventBadge source={event.source} />
                    </TableCell>
                    <TableCell
                      className="text-sm"
                      data-testid={`audit-feed-summary-${event.id}`}
                    >
                      {event.summary}
                    </TableCell>
                    <TableCell
                      className="text-xs uppercase tracking-wide text-muted-foreground"
                      data-testid={`audit-feed-action-${event.id}`}
                    >
                      {event.action}
                    </TableCell>
                    <TableCell
                      className="text-sm"
                      data-testid={`audit-feed-entity-${event.id}`}
                      title={event.entity_id}
                    >
                      <span className="text-muted-foreground">
                        {ENTITY_LABEL[event.entity_type]}
                      </span>{" "}
                      <span className="font-mono text-xs">
                        {shortId(event.entity_id)}
                      </span>
                    </TableCell>
                    <TableCell
                      className="font-mono text-xs"
                      data-testid={`audit-feed-actor-${event.id}`}
                      title={event.actor_id ?? SYSTEM_PLACEHOLDER}
                    >
                      {event.actor_id === null
                        ? SYSTEM_PLACEHOLDER
                        : shortId(event.actor_id)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
