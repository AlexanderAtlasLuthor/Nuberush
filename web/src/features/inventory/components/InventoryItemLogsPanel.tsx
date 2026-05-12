// F2.6.2 subfase 4: inventory item audit-log panel.
//
// Self-contained read-only panel: takes an inventoryItemId and owns its
// own data fetch via `useInventoryItemLogs(inventoryItemId)`. Manages
// loading / error / empty / success states inside its own Card.
//
// Hard rules in force:
//   - No fetch, no mutations, no Zustand, no actions.
//   - Append-only audit rows are rendered verbatim. The frontend never
//     decides which movement types are "good" or "bad" — there is no
//     severity mapping, no inferred labels, no inventory math.
//   - Missing fields render as the em-dash placeholder. We never
//     compute or fabricate values.
//
// Pagination model:
//   The backend wire is `list[InventoryLogRead]` and only accepts a
//   `limit` query param — there is NO server-side offset / total. To
//   honour the brief's Previous / Next UX without lying about server
//   capabilities, we fetch a generous batch (DEFAULT_FETCH_LIMIT) and
//   page over it in memory (PAGE_SIZE = 20). `total` here means
//   "rows in the fetched batch", not the row count in the DB. If the
//   audit history grows past the fetch ceiling, the operator only sees
//   the most recent slice — explicit by design until the wire grows
//   real pagination.

import { useState } from "react";
import { History } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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

import { useInventoryItemLogs } from "../hooks";

const EM_DASH = "—";
const PAGE_SIZE = 20;
const DEFAULT_FETCH_LIMIT = 200;

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

function nullableNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? EM_DASH : String(value);
}

interface InventoryItemLogsPanelProps {
  inventoryItemId: string;
}

export function InventoryItemLogsPanel({
  inventoryItemId,
}: InventoryItemLogsPanelProps) {
  const [offset, setOffset] = useState(0);

  const { isLoading, isError, error, data: logs, refetch } =
    useInventoryItemLogs(inventoryItemId, { limit: DEFAULT_FETCH_LIMIT });

  const total = logs?.length ?? 0;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);
  const pageRows = logs ? logs.slice(offset, pageEnd) : [];

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  const handlePrev = () => {
    setOffset((prev) => Math.max(0, prev - PAGE_SIZE));
  };

  const handleNext = () => {
    setOffset((prev) => prev + PAGE_SIZE);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit log</CardTitle>
        <CardDescription>
          One row per stock movement (append-only).
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <LoadingState message="Loading audit log..." />
        ) : isError ? (
          <ErrorState
            title="Audit log failed to load"
            message={getApiErrorMessage(error)}
            onRetry={() => refetch()}
          />
        ) : logs && logs.length === 0 ? (
          <EmptyState
            icon={History}
            title="No audit entries"
            message="No stock movements have been recorded for this item yet."
          />
        ) : logs ? (
          <div className="rounded-b-md border-t border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Movement</TableHead>
                  <TableHead>Δ qty</TableHead>
                  <TableHead>Qty after</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Performed by</TableHead>
                  <TableHead>Created at</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageRows.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {log.movement_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      {nullableNumber(log.quantity_delta)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {nullableNumber(log.quantity_after)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {nullableText(log.reason)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {log.reference_type || log.reference_id ? (
                        <>
                          <span className="text-xs uppercase tracking-wide text-muted-foreground">
                            {nullableText(log.reference_type)}
                          </span>{" "}
                          <span className="font-mono text-xs">
                            {nullableText(log.reference_id)}
                          </span>
                        </>
                      ) : (
                        EM_DASH
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {nullableText(log.performed_by_user_id)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {log.created_at}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
      {logs && total > 0 ? (
        <CardFooter className="flex items-center justify-between gap-2 px-6 py-3 text-xs text-muted-foreground">
          <span data-testid="inventory-logs-page-meta">
            Showing {total === 0 ? 0 : offset + 1}–{pageEnd} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePrev}
              disabled={!canPrev}
              data-testid="inventory-logs-prev"
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleNext}
              disabled={!canNext}
              data-testid="inventory-logs-next"
            >
              Next
            </Button>
          </div>
        </CardFooter>
      ) : null}
    </Card>
  );
}
