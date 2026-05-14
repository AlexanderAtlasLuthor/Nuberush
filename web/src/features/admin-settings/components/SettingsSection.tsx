// Generic settings section: titled card with a definition-list grid
// of key/value pairs. Pure presentational; consumers pass the
// backend-computed values directly. No business logic, no fetching.

import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface SettingsField {
  /** Stable key used for React reconciliation and `data-testid`. */
  key: string;
  /** Human label rendered as the field's `<dt>`. */
  label: string;
  /** Pre-rendered value (string, badge, list, …). */
  value: ReactNode;
  /** Optional small helper line below the value. */
  hint?: string;
}

export interface SettingsSectionProps {
  title: string;
  description?: string;
  fields: SettingsField[];
  testId: string;
}

export function SettingsSection({
  title,
  description,
  fields,
  testId,
}: SettingsSectionProps) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="p-5 pb-3 space-y-1">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </CardHeader>
      <CardContent className="p-5 pt-0">
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          {fields.map((field) => (
            <div
              key={field.key}
              data-testid={`${testId}-field-${field.key}`}
              className="space-y-1"
            >
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {field.label}
              </dt>
              <dd
                className="text-sm font-medium text-foreground"
                data-testid={`${testId}-value-${field.key}`}
              >
                {field.value}
              </dd>
              {field.hint ? (
                <p className="text-xs text-muted-foreground">{field.hint}</p>
              ) : null}
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
