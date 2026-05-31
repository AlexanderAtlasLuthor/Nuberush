// F2.24.C6 — Step 3 (Owner / contact information). Presentational.

import { WizardField } from "./WizardField";
import type {
  ApplicationFormErrors,
  ApplicationFormValues,
  FieldChange,
} from "./form";

export interface OwnerInfoStepProps {
  values: ApplicationFormValues;
  errors: ApplicationFormErrors;
  onChange: FieldChange;
  disabled?: boolean;
}

export function OwnerInfoStep({
  values,
  errors,
  onChange,
  disabled,
}: OwnerInfoStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Owner &amp; contact
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This person should be authorized to represent the store. If the
          application is approved, this email will be used to set up owner
          access.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <WizardField
            id="owner_full_name"
            label="Owner full name"
            value={values.owner_full_name}
            onChange={(v) => onChange("owner_full_name", v)}
            error={errors.owner_full_name}
            required
            maxLength={150}
            autoComplete="name"
            disabled={disabled}
          />
        </div>
        <WizardField
          id="owner_email"
          label="Owner email"
          value={values.owner_email}
          onChange={(v) => onChange("owner_email", v)}
          error={errors.owner_email}
          required
          type="email"
          inputMode="email"
          maxLength={255}
          autoComplete="email"
          disabled={disabled}
        />
        <WizardField
          id="owner_phone"
          label="Owner phone"
          value={values.owner_phone}
          onChange={(v) => onChange("owner_phone", v)}
          error={errors.owner_phone}
          required
          type="tel"
          inputMode="tel"
          maxLength={30}
          autoComplete="tel"
          disabled={disabled}
        />
      </div>
    </div>
  );
}

export default OwnerInfoStep;
