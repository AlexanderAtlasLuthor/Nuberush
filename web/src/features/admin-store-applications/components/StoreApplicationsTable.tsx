// F2.24.C7: store-applications queue — desktop table + mobile cards.
//
// Pure presentation. Receives the already-fetched applications and the
// loading/error flags; renders the shared stateful surfaces or the data.
// No data fetching, no filter state — those live in the page. The desktop
// <table> is hidden on small screens; StoreApplicationMobileCards is
// hidden on md+, so exactly one representation shows per breakpoint.

import { Link } from "react-router-dom";
import { ClipboardList } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { getApiErrorMessage } from "@/api";

import { StoreApplicationStatusBadge } from "./StoreApplicationStatusBadge";
import { StoreApplicationMobileCards } from "./StoreApplicationMobileCards";
import { formatApplicationDate } from "./format";
import type { StoreApplicationListItem } from "../types";

export interface StoreApplicationsTableProps {
  applications: StoreApplicationListItem[];
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
}

export function StoreApplicationsTable({
  applications,
  isLoading = false,
  error,
  onRetry,
}: StoreApplicationsTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading applications…" />;
  }
  if (error) {
    return (
      <ErrorState
        title="Could not load applications"
        message={getApiErrorMessage(error)}
        onRetry={onRetry}
      />
    );
  }
  if (applications.length === 0) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="No applications found"
        message="No merchant applications match the current filters."
      />
    );
  }

  return (
    <>
      {/* Desktop: table. Hidden on small screens. */}
      <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Business</TableHead>
              <TableHead scope="col">Type</TableHead>
              <TableHead scope="col">Owner</TableHead>
              <TableHead scope="col">Email</TableHead>
              <TableHead scope="col">Location</TableHead>
              <TableHead scope="col">Status</TableHead>
              <TableHead scope="col">Submitted</TableHead>
              <TableHead scope="col">Reviewed</TableHead>
              <TableHead scope="col">
                <span className="sr-only">Review</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applications.map((application) => (
              <TableRow
                key={application.id}
                data-testid="store-application-row"
              >
                <TableCell className="font-medium">
                  <Link
                    to={`/app/admin/applications/${application.id}`}
                    className="text-primary hover:underline"
                    data-testid="store-application-link"
                  >
                    {application.business_name}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {application.business_type}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {application.owner_full_name}
                </TableCell>
                <TableCell className="break-all text-muted-foreground">
                  {application.owner_email}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {application.city}, {application.state}
                </TableCell>
                <TableCell>
                  <StoreApplicationStatusBadge status={application.status} />
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatApplicationDate(application.submitted_at)}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatApplicationDate(application.reviewed_at)}
                </TableCell>
                <TableCell className="text-right">
                  <Link
                    to={`/app/admin/applications/${application.id}`}
                    className="text-sm text-primary hover:underline"
                    data-testid="store-application-review-link"
                  >
                    Review
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile: stacked cards. Hidden on md+. */}
      <StoreApplicationMobileCards applications={applications} />
    </>
  );
}
