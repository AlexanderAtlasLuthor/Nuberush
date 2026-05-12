// F2.10.3: store-scoped inventory logs panel.
//
// Self-contained read-only panel: takes a `storeId` prop and owns its
// own data fetch via `useStoreInventoryLogsQuery({ storeId, limit })`.
// Manages no-store / loading / error / empty / success states inside
// its own Card. Designed to be mounted by the F2.10.4 AuditPage which
// will pass `useStoreContext().currentStoreId` as `storeId`.
//
// Hard rules in force:
//   - No fetch, no Zustand, no mutations, no actions.
//   - No useAuth, no currentUser, no role-based gating. Backend
//     authorises every read (`require_staff_or_above` +
//     `require_store_member`) and 401/403/404 surface through the
//     centralized ApiError path.
//   - No useStoreContext inside the panel itself — the page is
//     responsible for resolving the current store and passing it in.
//     Keeping the panel storeId-agnostic also makes it reusable from
//     a future admin store-picker without coupling to session state.
//   - No client-side sorting, merging, or aggregation. Rows are
//     rendered exactly in the order the backend returned them
//     (DESC by created_at server-side).
//   - No client-side filtering — the only forwarded param is `limit`,
//     which is the only filter the backend route accepts.
//   - No "global audit feed" copy — the empty/no-store/header strings
//     are explicit about being store-scoped inventory logs only.
//
// Pagination model:
//   None. The backend wire is `list[InventoryLogRead]` and only
//   accepts `limit` (no offset, no total). The panel forwards `limit`
//   if provided and renders every returned row. The F2.10.0 diagnostic
//   ruled out fake pagination for this MVP — do not add a Previous/Next
//   here without a backend wire change.

import { History, Store as StoreIcon } from "lucide-react";

import { getApiErrorMessage } from "@/api";
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

import { useStoreInventoryLogsQuery } from "../hooks";

const EM_DASH = "—";
const SYSTEM_PLACEHOLDER = "System";

// `Intl.NumberFormat` with `signDisplay: "exceptZero"` renders "+10",
// "-3", "0". Backend has a CHECK CONSTRAINT `quantity_delta <> 0`, so
// the zero branch is defensive only.
const SIGNED_QTY_FORMAT = new Intl.NumberFormat("en-US", {
  signDisplay: "exceptZero",
});

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

function formatSignedDelta(value: number): string {
  return SIGNED_QTY_FORMAT.format(value);
}

export interface StoreInventoryLogsPanelProps {
  /**
   * Store UUID, or null/undefined when no store is selected. The hook
   * stays disabled while this is unusable, and the panel renders the
   * "no store selected" state instead of touching the network.
   */
  storeId: string | null | undefined;
  /**
   * Maximum rows to fetch from the backend. Forwarded verbatim. Omit
   * to use the backend default (100). No client-side pagination is
   * applied; whatever the backend returns is rendered.
   */
  limit?: number;
  className?: string;
}

export function StoreInventoryLogsPanel({
  storeId,
  limit,
  className,
}: StoreInventoryLogsPanelProps) {
  const trimmedStoreId =
    typeof storeId === "string" ? storeId.trim() : "";
  const hasStore = trimmedStoreId.length > 0;

  const { isLoading, isError, error, data: logs, refetch } =
    useStoreInventoryLogsQuery({ storeId, limit });

  return (
    <Card className={className} data-testid="store-inventory-logs-panel">
      <CardHeader>
        <CardTitle>Store inventory logs</CardTitle>
        <CardDescription>
          Append-only stock-movement audit trail for the selected store.
          Rows are produced server-side by inventory movements; the
          frontend never invents events or reorders rows.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {!hasStore ? (
          <EmptyState
            icon={StoreIcon}
            title="No store selected"
            message="Select a store to view inventory logs."
          />
        ) : isLoading ? (
          <LoadingState message="Loading inventory logs…" />
        ) : isError ? (
          <ErrorState
            title="Inventory logs failed to load"
            message={getApiErrorMessage(error)}
            onRetry={() => refetch()}
          />
        ) : logs && logs.length === 0 ? (
          <EmptyState
            icon={History}
            title="No inventory logs"
            message="No inventory logs found for this store yet."
          />
        ) : logs ? (
          <div
            className="rounded-b-md border-t border-border"
            data-testid="store-inventory-logs-table-wrapper"
          >
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
                {logs.map((log) => (
                  <TableRow
                    key={log.id}
                    data-testid={`store-inventory-logs-row-${log.id}`}
                  >
                    <TableCell>
                      <span
                        className="text-xs uppercase tracking-wide text-muted-foreground"
                        data-testid={`store-inventory-logs-movement-${log.id}`}
                      >
                        {log.movement_type}
                      </span>
                    </TableCell>
                    <TableCell
                      className="text-sm font-mono"
                      data-testid={`store-inventory-logs-delta-${log.id}`}
                    >
                      {formatSignedDelta(log.quantity_delta)}
                    </TableCell>
                    <TableCell
                      className="text-sm font-mono"
                      data-testid={`store-inventory-logs-qty-after-${log.id}`}
                    >
                      {log.quantity_after}
                    </TableCell>
                    <TableCell
                      className="text-sm"
                      data-testid={`store-inventory-logs-reason-${log.id}`}
                    >
                      {nullableText(log.reason)}
                    </TableCell>
                    <TableCell
                      className="text-sm"
                      data-testid={`store-inventory-logs-reference-${log.id}`}
                    >
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
                    <TableCell
                      className="font-mono text-xs"
                      data-testid={`store-inventory-logs-performer-${log.id}`}
                    >
                      {log.performed_by_user_id ?? SYSTEM_PLACEHOLDER}
                    </TableCell>
                    <TableCell
                      className="whitespace-nowrap text-sm text-muted-foreground"
                      data-testid={`store-inventory-logs-created-${log.id}`}
                    >
                      {log.created_at}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
