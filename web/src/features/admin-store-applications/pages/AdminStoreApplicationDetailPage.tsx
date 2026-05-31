// F2.24.C7: Admin store-application detail / review page.
//
// Mounted at /app/admin/applications/:applicationId under AdminShell.
// Shows the full application (business / owner / operations / status /
// audit) and, only while the application is still pending_review, the
// approve panel and reject action. Non-pending applications are
// read-only — no active approve/reject controls.
//
// Architecture rules (mirroring features/stores AdminStoreDetailPage):
//   - No fetch, no Supabase. Hooks do the talking.
//   - useAdminStoreApplicationQuery accepts undefined/"" and short-
//     circuits via its `enabled` flag when the route has no id.
//   - No useAuth / role checks. Backend RBAC is authoritative.

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";

import { ApplicationReviewSummary } from "../components/ApplicationReviewSummary";
import { ApproveApplicationPanel } from "../components/ApproveApplicationPanel";
import { RejectApplicationDialog } from "../components/RejectApplicationDialog";
import { useAdminStoreApplicationQuery } from "../hooks";

export default function AdminStoreApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const [rejectOpen, setRejectOpen] = useState(false);

  const query = useAdminStoreApplicationQuery(applicationId);

  const renderBody = () => {
    if (!applicationId || applicationId.length === 0) {
      return (
        <EmptyState
          title="Missing application id"
          message="This page requires an application id in the URL."
        />
      );
    }
    if (query.isLoading) {
      return <LoadingState message="Loading application…" />;
    }
    if (query.isError) {
      return (
        <ErrorState
          title="Could not load application"
          message={getApiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      );
    }
    if (!query.data) {
      return (
        <EmptyState
          title="No application data"
          message="The backend returned no application for this id."
        />
      );
    }

    const application = query.data;
    const isPending = application.status === "pending_review";

    return (
      <>
        {isPending ? (
          <div
            className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end"
            data-testid="application-review-actions"
          >
            <Button
              type="button"
              variant="destructive"
              onClick={() => setRejectOpen(true)}
              data-testid="application-reject-button"
            >
              Reject application
            </Button>
          </div>
        ) : null}

        {isPending ? <ApproveApplicationPanel application={application} /> : null}

        <ApplicationReviewSummary application={application} />

        <RejectApplicationDialog
          application={application}
          open={rejectOpen}
          onOpenChange={setRejectOpen}
        />
      </>
    );
  };

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-4xl"
      data-testid="admin-store-application-detail-page"
    >
      <div>
        <Link
          to="/app/admin/applications"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          data-testid="application-detail-back-link"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to applications
        </Link>
      </div>

      <header>
        <h1 className="text-xl font-semibold">Application review</h1>
        <p className="text-sm text-muted-foreground">
          Platform-level review of a single merchant application.
        </p>
      </header>

      {renderBody()}
    </div>
  );
}
