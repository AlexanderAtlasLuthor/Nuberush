// F2.24.C6 — Step 2 (Business information). Presentational; the wizard
// owns state, validation and navigation.

import { WizardField } from "./WizardField";
import type {
  ApplicationFormErrors,
  ApplicationFormValues,
  FieldChange,
} from "./form";

export interface BusinessInfoStepProps {
  values: ApplicationFormValues;
  errors: ApplicationFormErrors;
  onChange: FieldChange;
  disabled?: boolean;
}

export function BusinessInfoStep({
  values,
  errors,
  onChange,
  disabled,
}: BusinessInfoStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Business information
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Tell us about the store you'd like to bring onto NubeRush.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <WizardField
          id="business_name"
          label="Business name"
          value={values.business_name}
          onChange={(v) => onChange("business_name", v)}
          error={errors.business_name}
          required
          maxLength={200}
          autoComplete="organization"
          disabled={disabled}
        />
        <WizardField
          id="business_type"
          label="Business type"
          value={values.business_type}
          onChange={(v) => onChange("business_type", v)}
          error={errors.business_type}
          required
          maxLength={100}
          placeholder="e.g. Convenience store"
          disabled={disabled}
        />
        <WizardField
          id="business_phone"
          label="Business phone"
          value={values.business_phone}
          onChange={(v) => onChange("business_phone", v)}
          error={errors.business_phone}
          required
          type="tel"
          inputMode="tel"
          maxLength={30}
          autoComplete="tel"
          disabled={disabled}
        />
        <WizardField
          id="location_count"
          label="Number of locations"
          value={values.location_count}
          onChange={(v) => onChange("location_count", v)}
          error={errors.location_count}
          required
          type="number"
          inputMode="numeric"
          min={1}
          disabled={disabled}
        />
        <WizardField
          id="estimated_weekly_orders"
          label="Estimated weekly orders"
          value={values.estimated_weekly_orders}
          onChange={(v) => onChange("estimated_weekly_orders", v)}
          error={errors.estimated_weekly_orders}
          required
          type="number"
          inputMode="numeric"
          min={0}
          disabled={disabled}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <WizardField
            id="address_line_1"
            label="Street address"
            value={values.address_line_1}
            onChange={(v) => onChange("address_line_1", v)}
            error={errors.address_line_1}
            required
            maxLength={200}
            autoComplete="address-line1"
            disabled={disabled}
          />
        </div>
        <div className="sm:col-span-2">
          <WizardField
            id="address_line_2"
            label="Suite / unit"
            value={values.address_line_2}
            onChange={(v) => onChange("address_line_2", v)}
            optionalHint="optional"
            maxLength={200}
            autoComplete="address-line2"
            disabled={disabled}
          />
        </div>
        <WizardField
          id="city"
          label="City"
          value={values.city}
          onChange={(v) => onChange("city", v)}
          error={errors.city}
          required
          maxLength={120}
          autoComplete="address-level2"
          disabled={disabled}
        />
        <WizardField
          id="state"
          label="State / region"
          value={values.state}
          onChange={(v) => onChange("state", v)}
          error={errors.state}
          required
          maxLength={120}
          autoComplete="address-level1"
          disabled={disabled}
        />
        <WizardField
          id="postal_code"
          label="Postal code"
          value={values.postal_code}
          onChange={(v) => onChange("postal_code", v)}
          error={errors.postal_code}
          required
          maxLength={20}
          autoComplete="postal-code"
          disabled={disabled}
        />
        <WizardField
          id="country"
          label="Country code"
          value={values.country}
          onChange={(v) => onChange("country", v)}
          error={errors.country}
          required
          maxLength={2}
          placeholder="US"
          autoComplete="country"
          disabled={disabled}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <WizardField
          id="website_url"
          label="Website"
          value={values.website_url}
          onChange={(v) => onChange("website_url", v)}
          optionalHint="optional"
          type="url"
          inputMode="url"
          maxLength={255}
          placeholder="https://"
          disabled={disabled}
        />
        <WizardField
          id="social_url"
          label="Social profile"
          value={values.social_url}
          onChange={(v) => onChange("social_url", v)}
          optionalHint="optional"
          type="url"
          inputMode="url"
          maxLength={255}
          placeholder="https://"
          disabled={disabled}
        />
      </div>
    </div>
  );
}

export default BusinessInfoStep;
