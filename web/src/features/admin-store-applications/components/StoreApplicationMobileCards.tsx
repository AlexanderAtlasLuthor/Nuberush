// F2.24.C7: mobile card stack for the store-applications queue.
//
// Pure presentation. Renders one tappable card per application for small
// screens (the desktop table lives in StoreApplicationsTable, which hides
// this on md+). No loading/error/empty handling here — the parent owns
// those states.

import { Link } from "react-router-dom";

import { StoreApplicationStatusBadge } from "./StoreApplicationStatusBadge";
import { formatApplicationDate } from "./format";
import type { StoreApplicationListItem } from "../types";

export interface StoreApplicationMobileCardsProps {
  applications: StoreApplicationListItem[];
}

export function StoreApplicationMobileCards({
  applications,
}: StoreApplicationMobileCardsProps) {
  return (
    <div
      className="space-y-3 md:hidden"
      data-testid="store-applications-cards"
    >
      {applications.map((application) => (
        <Link
          key={application.id}
          to={`/app/admin/applications/${application.id}`}
          className="block rounded-lg border border-border p-4"
          data-testid="store-application-card"
        >
          <div className="flex items-start justify-between gap-2">
            <span className="font-medium">{application.business_name}</span>
            <StoreApplicationStatusBadge status={application.status} />
          </div>
          <dl className="mt-2 space-y-1 text-sm text-muted-foreground">
            <div className="flex justify-between gap-2">
              <dt>Type</dt>
              <dd>{application.business_type}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Owner</dt>
              <dd className="text-right">{application.owner_full_name}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Email</dt>
              <dd className="break-all text-right">{application.owner_email}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Location</dt>
              <dd className="text-right">
                {application.city}, {application.state}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Submitted</dt>
              <dd>{formatApplicationDate(application.submitted_at)}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Reviewed</dt>
              <dd>{formatApplicationDate(application.reviewed_at)}</dd>
            </div>
          </dl>
        </Link>
      ))}
    </div>
  );
}
