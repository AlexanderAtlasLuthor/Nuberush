import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

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
    <section aria-label="Call to action" className="w-full py-12 md:py-16">
      <div className="container">
        <div className="premium-ring mx-auto max-w-4xl rounded-[2rem] p-px text-center">
          <div className="premium-glass rounded-[2rem] px-5 py-9 md:px-10 md:py-11">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground md:text-4xl">
              {title}
            </h2>
            {description && (
              <p className="mx-auto mt-3 max-w-2xl text-base leading-relaxed text-foreground/64">
                {description}
              </p>
            )}
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                to={primary.to}
                className="premium-action inline-flex h-10 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {primary.label}
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              {secondary && (
                <Link
                  to={secondary.to}
                  className="inline-flex h-10 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-5 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {secondary.label}
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default PublicCtaBand;
