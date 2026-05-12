// Pure presentational placeholder. No data fetch, no mock data, no router hooks.

import type { LucideIcon } from "lucide-react";

interface FeaturePlaceholderProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  status?: string;
  requiredBackend?: string[];
  nonGoals?: string[];
  futureCapabilities?: string[];
}

export function FeaturePlaceholder({
  title,
  description,
  icon: Icon,
  status = "Planned",
  requiredBackend = [],
  nonGoals = [],
  futureCapabilities = [],
}: FeaturePlaceholderProps) {
  return (
    <div className="p-6 md:p-8 max-w-4xl space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          {Icon ? (
            <Icon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          ) : null}
          <h1 className="text-xl font-semibold">{title}</h1>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
      </header>

      <section className="rounded-lg border border-border p-5">
        <h2 className="text-sm font-semibold">Status</h2>
        <p className="mt-3 text-sm text-muted-foreground">{status}</p>
      </section>

      {futureCapabilities.length > 0 ? (
        <section className="rounded-lg border border-border p-5">
          <h2 className="text-sm font-semibold">Future capabilities</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {futureCapabilities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {requiredBackend.length > 0 ? (
        <section className="rounded-lg border border-dashed border-border p-5">
          <h2 className="text-sm font-semibold">Backend required</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {requiredBackend.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {nonGoals.length > 0 ? (
        <section className="rounded-lg border border-border p-5">
          <h2 className="text-sm font-semibold">Not simulated in frontend</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {nonGoals.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
