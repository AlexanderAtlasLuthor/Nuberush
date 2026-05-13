import { Link } from "react-router-dom";

interface CtaLink {
  label: string;
  to: string;
}

interface PublicHeroProps {
  eyebrow?: string;
  headline: string;
  subhead?: string;
  primary: CtaLink;
  secondary?: CtaLink;
}

export function PublicHero({
  eyebrow,
  headline,
  subhead,
  primary,
  secondary,
}: PublicHeroProps) {
  return (
    <section
      aria-label="Hero"
      className="w-full bg-background border-b border-border"
    >
      <div className="container max-w-4xl py-20 md:py-28 text-center">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-3 text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tight text-foreground leading-tight">
          {headline}
        </h1>
        {subhead && (
          <p className="mt-5 text-base md:text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
            {subhead}
          </p>
        )}
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            to={primary.to}
            className="inline-flex items-center justify-center h-11 px-6 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            {primary.label}
          </Link>
          {secondary && (
            <Link
              to={secondary.to}
              className="inline-flex items-center justify-center h-11 px-6 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {secondary.label}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

export default PublicHero;
