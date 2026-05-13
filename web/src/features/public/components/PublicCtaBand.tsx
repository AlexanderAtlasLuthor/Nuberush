import { Link } from "react-router-dom";

interface CtaLink {
  label: string;
  to: string;
}

interface PublicCtaBandProps {
  title: string;
  description?: string;
  primary: CtaLink;
  secondary?: CtaLink;
}

export function PublicCtaBand({
  title,
  description,
  primary,
  secondary,
}: PublicCtaBandProps) {
  return (
    <section
      aria-label="Call to action"
      className="w-full border-y border-border bg-card/40 py-12 md:py-16"
    >
      <div className="container max-w-4xl text-center">
        <h2 className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        {description && (
          <p className="mt-3 text-base text-muted-foreground leading-relaxed">
            {description}
          </p>
        )}
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            to={primary.to}
            className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            {primary.label}
          </Link>
          {secondary && (
            <Link
              to={secondary.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {secondary.label}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

export default PublicCtaBand;
