// F2.7.3: order audit logs panel.
//
// Self-contained read-only panel: takes an orderId and owns its own
// data fetch via `useOrderAuditLogs(orderId)`. Manages loading / error
// / empty / success states inside its own Card. Mounted by
// OrderDetailPage (and reusable by any future page that needs the
// audit trail of an order — e.g. a manager review screen).
//
// Hard rules in force:
//   - No fetch, no Zustand, no mutations, no actions.
//   - No state machine logic — `previous_status` / `new_status` /
//     `action` are rendered verbatim. The frontend never decides
//     which transitions are valid.
//   - No date formatting beyond raw ISO display. Polishing dates is
//     a future UI concern, not a panel responsibility.
//
// The previous F2.7.2 implementation embedded this same UI inline in
// OrderDetailPage. Extracting it changes one observable behavior:
// `useOrderAuditLogs` is now only called when the panel is actually
// mounted (i.e. when the order detail succeeded), instead of being
// called unconditionally alongside the order query. Net effect:
// fewer pointless audit fetches when the order itself failed to load.

import { History } from "lucide-react";

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

import { useOrderAuditLogs } from "../hooks";

const EM_DASH = "—";

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

interface OrderAuditLogsPanelProps {
  orderId: string;
}

export function OrderAuditLogsPanel({ orderId }: OrderAuditLogsPanelProps) {
  const { isLoading, isError, error, data: logs, refetch } =
    useOrderAuditLogs(orderId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit log</CardTitle>
        <CardDescription>
          One row per state transition (append-only).
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
            message="No state transitions have been recorded for this order yet."
          />
        ) : logs ? (
          <div className="rounded-b-md border-t border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Previous</TableHead>
                  <TableHead>New</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Performed by</TableHead>
                  <TableHead>Created at</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {nullableText(log.previous_status)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {log.new_status}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">{log.action}</TableCell>
                    <TableCell className="text-sm">
                      {nullableText(log.reason)}
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
    </Card>
  );
}
