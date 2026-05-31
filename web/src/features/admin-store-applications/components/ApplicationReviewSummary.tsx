// F2.24.C7: read-only review summary for a single store application.
//
// Renders every submitted business / owner / operations field plus the
// server-owned review state (status, timestamps, reviewer, rejection
// reason, provisioned store/owner ids) and the audit-log trail. No
// actions — the detail page composes this with the approve panel and
// reject dialog. Sections use h2 headings under the page's single h1.

import { Separator } from "@/components/ui/separator";

import { StoreApplicationStatusBadge } from "./StoreApplicationStatusBadge";
import { formatApplicationDateTime } from "./format";
import type { StoreApplicationDetail } from "../types";

function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-base font-medium break-words">{value}</dd>
    </div>
  );
}

function text(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return value;
}

export interface ApplicationReviewSummaryProps {
  application: StoreApplicationDetail;
}

export function ApplicationReviewSummary({
  application,
}: ApplicationReviewSummaryProps) {
  const a = application;
  return (
    <div className="space-y-8" data-testid="application-review-summary">
      {/* Status + review state */}
      <section className="space-y-4" aria-labelledby="section-status">
        <h2 id="section-status" className="text-lg font-semibold">
          Status
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field
            label="Application status"
            value={<StoreApplicationStatusBadge status={a.status} />}
          />
          <Field label="Submitted" value={formatApplicationDateTime(a.submitted_at)} />
          <Field label="Reviewed" value={formatApplicationDateTime(a.reviewed_at)} />
          <Field label="Reviewed by" value={text(a.reviewed_by_user_id)} />
          {a.status === "rejected" ? (
            <div className="sm:col-span-2">
              <Field
                label="Rejection reason"
                value={
                  <span data-testid="application-rejection-reason">
                    {text(a.rejection_reason)}
                  </span>
                }
              />
            </div>
          ) : null}
          {a.provisioned_store_id ? (
            <Field
              label="Provisioned store id"
              value={
                <span
                  className="font-mono text-sm"
                  data-testid="application-provisioned-store-id"
                >
                  {a.provisioned_store_id}
                </span>
              }
            />
          ) : null}
          {a.provisioned_owner_user_id ? (
            <Field
              label="Provisioned owner id"
              value={
                <span
                  className="font-mono text-sm"
                  data-testid="application-provisioned-owner-id"
                >
                  {a.provisioned_owner_user_id}
                </span>
              }
            />
          ) : null}
        </dl>
      </section>

      <Separator />

      {/* Business information */}
      <section className="space-y-4" aria-labelledby="section-business">
        <h2 id="section-business" className="text-lg font-semibold">
          Business information
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Business name" value={text(a.business_name)} />
          <Field label="Business type" value={text(a.business_type)} />
          <Field label="Website" value={text(a.website_url)} />
          <Field label="Social" value={text(a.social_url)} />
        </dl>
      </section>

      <Separator />

      {/* Owner / contact information */}
      <section className="space-y-4" aria-labelledby="section-owner">
        <h2 id="section-owner" className="text-lg font-semibold">
          Owner &amp; contact
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Owner name" value={text(a.owner_full_name)} />
          <Field label="Owner email" value={text(a.owner_email)} />
          <Field label="Owner phone" value={text(a.owner_phone)} />
          <Field label="Business phone" value={text(a.business_phone)} />
          <Field label="Address line 1" value={text(a.address_line_1)} />
          <Field label="Address line 2" value={text(a.address_line_2)} />
          <Field label="City" value={text(a.city)} />
          <Field label="State" value={text(a.state)} />
          <Field label="Postal code" value={text(a.postal_code)} />
          <Field label="Country" value={text(a.country)} />
        </dl>
      </section>

      <Separator />

      {/* Operations information */}
      <section className="space-y-4" aria-labelledby="section-operations">
        <h2 id="section-operations" className="text-lg font-semibold">
          Operations
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Location count" value={String(a.location_count)} />
          <Field
            label="Estimated weekly orders"
            value={
              a.estimated_weekly_orders === null
                ? "—"
                : String(a.estimated_weekly_orders)
            }
          />
          <Field label="Hours of operation" value={text(a.hours_of_operation)} />
          <Field
            label="Terms accepted"
            value={a.terms_accepted ? "Yes" : "No"}
          />
          <div className="sm:col-span-2">
            <Field label="Notes" value={text(a.notes)} />
          </div>
        </dl>
      </section>

      <Separator />

      {/* Audit trail */}
      <section className="space-y-4" aria-labelledby="section-audit">
        <h2 id="section-audit" className="text-lg font-semibold">
          Audit log
        </h2>
        {a.audit_logs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No audit events recorded yet.
          </p>
        ) : (
          <ul className="space-y-3" data-testid="application-audit-logs">
            {a.audit_logs.map((log) => (
              <li
                key={log.id}
                className="rounded-md border border-border p-3 text-sm"
                data-testid="application-audit-log"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{log.event_type}</span>
                  <span className="text-muted-foreground">
                    {formatApplicationDateTime(log.created_at)}
                  </span>
                </div>
                {log.message ? (
                  <p className="mt-1 text-muted-foreground">{log.message}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
