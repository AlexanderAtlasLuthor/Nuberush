import type { TrustPoint } from "../content/publicCopy";

interface PublicTrustBandProps {
  points: ReadonlyArray<TrustPoint>;
}

export function PublicTrustBand({ points }: PublicTrustBandProps) {
  return (
    <section
      aria-label="Trust and positioning"
      className="w-full border-b border-border bg-card/40 py-10 md:py-12"
    >
      <div className="container">
        <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {points.map((point) => {
            const Icon = point.icon;
            return (
              <li key={point.title} className="flex items-start gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    {point.title}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                    {point.body}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

export default PublicTrustBand;
