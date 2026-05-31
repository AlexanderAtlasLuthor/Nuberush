// F2.24.C6 — Step 5 (Review + terms). Read-only summary of everything
// entered, plus the required confirmation checkbox that maps to
// `terms_accepted: true`.

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

import type { ApplicationFormErrors, ApplicationFormValues } from "./form";

export interface ReviewStepProps {
  values: ApplicationFormValues;
  errors: ApplicationFormErrors;
  onTermsChange: (accepted: boolean) => void;
  disabled?: boolean;
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm text-foreground sm:text-right">
        {value.trim() ? value : "—"}
      </dd>
    </div>
  );
}

export function ReviewStep({
  values,
  errors,
  onTermsChange,
  disabled,
}: ReviewStepProps) {
  const address = [
    values.address_line_1,
    values.address_line_2,
    [values.city, values.state, values.postal_code]
      .filter((p) => p.trim())
      .join(", "),
    values.country,
  ]
    .filter((p) => p.trim())
    .join(" · ");

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Review &amp; submit
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Please confirm the details below before submitting your
          application for review.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-5">
        <dl className="space-y-3">
          <SummaryRow label="Business" value={values.business_name} />
          <SummaryRow label="Type" value={values.business_type} />
          <SummaryRow label="Business phone" value={values.business_phone} />
          <SummaryRow label="Address" value={address} />
          <SummaryRow label="Locations" value={values.location_count} />
          <SummaryRow
            label="Weekly orders"
            value={values.estimated_weekly_orders}
          />
          <SummaryRow label="Website" value={values.website_url} />
          <SummaryRow label="Social" value={values.social_url} />
          <SummaryRow label="Owner" value={values.owner_full_name} />
          <SummaryRow label="Owner email" value={values.owner_email} />
          <SummaryRow label="Owner phone" value={values.owner_phone} />
          <SummaryRow label="Hours" value={values.hours_of_operation} />
          <SummaryRow label="Notes" value={values.notes} />
        </dl>
      </div>

      <div className="rounded-xl border border-border bg-muted/30 p-4">
        <div className="flex items-start gap-3">
          <Checkbox
            id="terms_accepted"
            checked={values.terms_accepted}
            onCheckedChange={(checked) => onTermsChange(checked === true)}
            disabled={disabled}
            aria-invalid={errors.terms_accepted ? true : undefined}
            aria-describedby={
              errors.terms_accepted ? "terms_accepted-error" : undefined
            }
            data-testid="apply-terms"
            className="mt-0.5"
          />
          <div className="space-y-1">
            <Label
              htmlFor="terms_accepted"
              className="text-sm font-normal leading-relaxed text-foreground"
            >
              I confirm that the information provided is accurate and that I
              am authorized to submit this application on behalf of this
              business.
            </Label>
            {errors.terms_accepted ? (
              <p
                id="terms_accepted-error"
                role="alert"
                className="text-sm text-destructive"
                data-testid="apply-error-terms_accepted"
              >
                {errors.terms_accepted}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Submitting an application does not guarantee approval. The NubeRush
        team reviews every store before activation.
      </p>
    </div>
  );
}

export default ReviewStep;
