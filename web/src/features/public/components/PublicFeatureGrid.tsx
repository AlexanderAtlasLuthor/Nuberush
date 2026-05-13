import type { FeatureCard } from "../content/publicCopy";

interface PublicFeatureGridProps {
  features: ReadonlyArray<FeatureCard>;
}

export function PublicFeatureGrid({ features }: PublicFeatureGridProps) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {features.map((feature) => {
        const Icon = feature.icon;
        return (
          <li
            key={feature.title}
            className="rounded-xl border border-border bg-card p-5"
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
            <p className="mt-4 text-sm font-semibold text-foreground">
              {feature.title}
            </p>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
              {feature.body}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

export default PublicFeatureGrid;
