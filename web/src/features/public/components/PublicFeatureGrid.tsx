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
            className="premium-glass-soft rounded-lg p-5 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/30"
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
            <p className="mt-4 text-sm font-semibold text-foreground">
              {feature.title}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-foreground/62">
              {feature.body}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

export default PublicFeatureGrid;
