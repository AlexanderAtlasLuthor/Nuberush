// F2.8.4: compliance audit log panel for the product detail page.
//
// Self-contained read-only panel: takes a productId and owns its own
// data fetch via `useProductComplianceAuditQuery(productId)`. Manages
// loading / error / empty / success states inside its own Card so a
// slow audit query never blocks the rest of the detail page.
//
// Hard rules in force:
//   - No fetch, no Zustand, no mutations.
//   - No transition validation: the previous → new compliance pair is
//     rendered verbatim. The frontend never decides which transitions
//     are valid (that lives in the backend service).
//   - No timestamp formatting beyond raw ISO display.
//   - The backend route is admin-only; non-admin callers will receive a
//     403 ApiError that surfaces through the shared ErrorState — we do
//     NOT pre-gate visibility on the frontend.

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

import { useProductComplianceAuditQuery } from "../hooks";

const EM_DASH = "—";

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

interface ProductComplianceAuditPanelProps {
  productId: string;
}

export function ProductComplianceAuditPanel({
  productId,
}: ProductComplianceAuditPanelProps) {
  const { isLoading, isError, error, data: logs, refetch } =
    useProductComplianceAuditQuery(productId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance audit log</CardTitle>
        <CardDescription>
          One row per compliance change (append-only). Admin-only on the backend.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <LoadingState message="Loading audit log…" />
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
            message="No compliance changes have been recorded for this product yet."
          />
        ) : logs ? (
          <div className="rounded-b-md border-t border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Old status</TableHead>
                  <TableHead>New status</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Changed by</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow
                    key={log.id}
                    data-testid="product-compliance-audit-row"
                  >
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {log.created_at}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {log.previous_compliance_status}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {log.new_compliance_status}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">{log.reason}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {nullableText(log.changed_by_user_id)}
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
