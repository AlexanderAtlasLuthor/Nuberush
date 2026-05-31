// F2.24.C6 — Step 4 (Store operations). Presentational. Hours required,
// notes optional. Uses Textarea for the free-text fields.

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import type {
  ApplicationFormErrors,
  ApplicationFormValues,
  FieldChange,
} from "./form";

export interface OperationsStepProps {
  values: ApplicationFormValues;
  errors: ApplicationFormErrors;
  onChange: FieldChange;
  disabled?: boolean;
}

export function OperationsStep({
  values,
  errors,
  onChange,
  disabled,
}: OperationsStepProps) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Store operations
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          A quick picture of how the store runs. You can keep this brief.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="hours_of_operation">
          Hours of operation<span className="text-destructive"> *</span>
        </Label>
        <Textarea
          id="hours_of_operation"
          name="hours_of_operation"
          value={values.hours_of_operation}
          onChange={(e) => onChange("hours_of_operation", e.target.value)}
          rows={3}
          placeholder="e.g. Mon–Sat 9am–9pm, Sun 10am–6pm"
          disabled={disabled}
          aria-invalid={errors.hours_of_operation ? true : undefined}
          aria-describedby={
            errors.hours_of_operation
              ? "hours_of_operation-error"
              : undefined
          }
          data-testid="apply-field-hours_of_operation"
        />
        {errors.hours_of_operation ? (
          <p
            id="hours_of_operation-error"
            role="alert"
            className="text-sm text-destructive"
            data-testid="apply-error-hours_of_operation"
          >
            {errors.hours_of_operation}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">
          Anything else
          <span className="text-muted-foreground"> (optional)</span>
        </Label>
        <Textarea
          id="notes"
          name="notes"
          value={values.notes}
          onChange={(e) => onChange("notes", e.target.value)}
          rows={4}
          placeholder="Anything that helps the NubeRush team review your store."
          disabled={disabled}
          data-testid="apply-field-notes"
        />
      </div>
    </div>
  );
}

export default OperationsStep;
