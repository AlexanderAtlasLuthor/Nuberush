// F2.20.6: presentational list of the most recent compliance review
// rows surfaced by `GET /admin/compliance`.
//
// Pure presentational: receives the bounded recent tail from the
// backend `AdminComplianceSummary.reviews` and renders one row per
// audit log entry. Never fetches, never derives compliance truth,
// never invents fields.
//
// Audit rows carry status transitions + reason + actor id + when.
// The product name does NOT live on the audit row (only product_id),
// so we render the short id; the operator can drill into the
// canonical product detail page via the queue table above to see
// the full product name. Inventing the name client-side here would
// require a second product-lookup query per row — that's outside
// F2.20.6's contract.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { ProductComplianceBadge } from "@/features/products/components/ProductComplianceBadge";
import type { ProductComplianceAuditLog } from "../types";

const EM_DASH = "—";

export interface RecentComplianceReviewsProps {
  reviews: ProductComplianceAuditLog[];
  recentCount: number;
}

function shortId(value: string | null): string {
  if (value === null) return EM_DASH;
  return value.length > 8 ? value.slice(0, 8) : value;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export function RecentComplianceReviews({
  reviews,
  recentCount,
}: RecentComplianceReviewsProps) {
  return (
    <Card data-testid="recent-compliance-reviews">
      <CardHeader>
        <CardTitle className="text-base">
          Recent compliance reviews{" "}
          <span
            className="text-sm font-normal text-muted-foreground"
            data-testid="recent-compliance-reviews-count"
          >
            ({recentCount})
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {reviews.length === 0 ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="recent-compliance-reviews-empty"
          >
            No recent compliance reviews on the platform.
          </p>
        ) : (
          <ul
            className="divide-y divide-border"
            data-testid="recent-compliance-reviews-list"
          >
            {reviews.map((review) => (
              <li
                key={review.id}
                className="py-3 flex flex-col gap-1 text-sm"
                data-testid="recent-compliance-reviews-row"
                data-review-id={review.id}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <ProductComplianceBadge
                    status={review.previous_compliance_status}
                  />
                  <span className="text-muted-foreground">→</span>
                  <ProductComplianceBadge
                    status={review.new_compliance_status}
                  />
                  <span className="text-xs text-muted-foreground">
                    Allowed for sale:{" "}
                    {review.previous_allowed_for_sale ? "Yes" : "No"} →{" "}
                    {review.new_allowed_for_sale ? "Yes" : "No"}
                  </span>
                </div>
                <p
                  className="text-sm"
                  data-testid="recent-compliance-reviews-reason"
                >
                  {review.reason}
                </p>
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <span data-testid="recent-compliance-reviews-product-id">
                    Product:{" "}
                    <span className="font-mono" title={review.product_id}>
                      {shortId(review.product_id)}
                    </span>
                  </span>
                  <span data-testid="recent-compliance-reviews-actor">
                    By:{" "}
                    <span
                      className="font-mono"
                      title={review.changed_by_user_id ?? undefined}
                    >
                      {shortId(review.changed_by_user_id)}
                    </span>
                  </span>
                  <span data-testid="recent-compliance-reviews-created-at">
                    {formatTimestamp(review.created_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
