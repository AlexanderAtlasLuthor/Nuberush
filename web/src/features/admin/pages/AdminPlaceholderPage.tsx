interface AdminPlaceholderPageProps {
  title: string;
  description: string;
  requiredBackend?: string[];
  nonGoals?: string[];
  futureCapabilities?: string[];
  routeContext?: string[];
}

export default function AdminPlaceholderPage({
  title,
  description,
  requiredBackend = [],
  nonGoals = [],
  futureCapabilities = [],
  routeContext = [],
}: AdminPlaceholderPageProps) {
  return (
    <div className="p-6 md:p-8 space-y-6 max-w-4xl">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Admin App placeholder
        </p>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </header>

      <section className="rounded-lg border border-border p-5">
        <h2 className="text-sm font-semibold">Status</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Backend Required
        </p>
      </section>

      {routeContext.length > 0 ? (
        <section className="rounded-lg border border-border p-5">
          <h2 className="text-sm font-semibold">Route context</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {routeContext.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-lg border border-dashed border-border p-5">
        <h2 className="text-sm font-semibold">
          Required backend capabilities
        </h2>
        {requiredBackend.length > 0 ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {requiredBackend.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            Backend requirements are pending definition.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-border p-5">
        <h2 className="text-sm font-semibold">
          Not simulated in frontend
        </h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>This page does not call admin backend endpoints yet.</li>
          <li>No fake admin data is rendered.</li>
          {nonGoals.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
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
    </div>
  );
}
