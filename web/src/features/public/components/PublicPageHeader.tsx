import type { ReactNode } from "react";

interface PublicPageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PublicPageHeader({
  eyebrow,
  title,
  description,
  actions,
}: PublicPageHeaderProps) {
  return (
    <section className="w-full border-b border-border bg-background py-16 md:py-20">
      <div className="container max-w-4xl">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-2 text-3xl md:text-4xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-4 text-base md:text-lg text-muted-foreground leading-relaxed">
            {description}
          </p>
        )}
        {actions && <div className="mt-6 flex flex-wrap gap-3">{actions}</div>}
      </div>
    </section>
  );
}

export default PublicPageHeader;
