// F2.24.C6 — labeled input + inline error, shared across wizard steps.
//
// Presentational only. Keeps every field's label/required-mark/error
// markup consistent and accessible (htmlFor, aria-invalid, role="alert").

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface WizardFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  type?: string;
  inputMode?: "text" | "numeric" | "tel" | "email" | "url";
  maxLength?: number;
  min?: number;
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
  optionalHint?: string;
}

export function WizardField({
  id,
  label,
  value,
  onChange,
  error,
  required = false,
  type = "text",
  inputMode,
  maxLength,
  min,
  placeholder,
  autoComplete,
  disabled = false,
  optionalHint,
}: WizardFieldProps) {
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {label}
        {required ? (
          <span className="text-destructive"> *</span>
        ) : optionalHint ? (
          <span className="text-muted-foreground"> ({optionalHint})</span>
        ) : null}
      </Label>
      <Input
        id={id}
        name={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        type={type}
        inputMode={inputMode}
        maxLength={maxLength}
        min={min}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        data-testid={`apply-field-${id}`}
      />
      {error ? (
        <p
          id={errorId}
          role="alert"
          className="text-sm text-destructive"
          data-testid={`apply-error-${id}`}
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default WizardField;
