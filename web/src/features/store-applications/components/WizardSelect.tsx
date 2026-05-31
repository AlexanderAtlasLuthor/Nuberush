// F2.24 — labeled dropdown + inline error, shared across wizard steps.
//
// Presentational only, and a sibling to WizardField: same label / required
// mark / error markup and the same `apply-field-${id}` / `apply-error-${id}`
// test hooks, so the wizard can swap a free-text field for a constrained
// dropdown without the orchestrator or tests caring which it is.
//
// Uses a NATIVE <select> on purpose: it's keyboard- and screen-reader-
// accessible out of the box, works under jsdom via fireEvent.change, and a
// dropdown can't hold an out-of-range value, so the numeric/location fields
// no longer need free-text validation.

import { ChevronDown } from "lucide-react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface WizardSelectOption {
  value: string;
  label: string;
}

export interface WizardSelectProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<WizardSelectOption>;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  optionalHint?: string;
  /** Placeholder shown as a disabled first option when value is empty. */
  placeholder?: string;
}

export function WizardSelect({
  id,
  label,
  value,
  onChange,
  options,
  error,
  required = false,
  disabled = false,
  optionalHint,
  placeholder,
}: WizardSelectProps) {
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
      <div className="relative">
        <select
          id={id}
          name={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          required={required}
          aria-label={label}
          aria-invalid={error ? true : undefined}
          aria-describedby={errorId}
          data-testid={`apply-field-${id}`}
          className={cn(
            "flex h-10 w-full appearance-none rounded-md border border-input bg-background px-3 pr-9 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            value.length === 0 ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {placeholder ? (
            // Intentionally NOT `disabled`: a disabled empty option makes a
            // controlled <select> impossible to drive via fireEvent.change in
            // jsdom (the value won't change). Required validation still blocks
            // a blank submit, so an empty-but-selectable placeholder is safe.
            <option value="">{placeholder}</option>
          ) : null}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
      </div>
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

export default WizardSelect;
