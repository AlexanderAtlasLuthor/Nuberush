import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { useMobileCopy } from "./useMobileCopy";

interface PublicPageHeaderProps {
  eyebrow?: string;
  title: string;
  mobileTitle?: string;
  description?: string;
  mobileDescription?: string;
  actions?: ReactNode;
}

export function PublicPageHeader({
  eyebrow,
  title,
  mobileTitle,
  description,
  mobileDescription,
  actions,
}: PublicPageHeaderProps) {
  const isMobileCopy = useMobileCopy();
  const displayTitle = isMobileCopy && mobileTitle ? mobileTitle : title;
  const displayDescription =
    isMobileCopy && mobileDescription ? mobileDescription : description;

  return (
    <section className="relative w-full overflow-hidden border-b border-foreground/10 pb-14 pt-28 md:py-20">
      <div className="absolute inset-x-0 top-0 -z-10 h-full bg-[radial-gradient(circle_at_18%_0%,hsl(var(--primary)/0.18),transparent_26rem)]" />
      <div className="container">
        <div className="premium-ring max-w-4xl rounded-[2rem] p-px">
          <div className="premium-glass rounded-[2rem] px-5 py-8 text-center md:px-8 md:py-10 md:text-left">
            {eyebrow && (
              <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                {eyebrow}
              </p>
            )}
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-foreground md:text-5xl">
              {displayTitle}
            </h1>
            {displayDescription && (
              <p className="mt-4 mx-auto max-w-3xl text-base leading-relaxed text-foreground/68 md:mx-0 md:text-lg">
                {displayDescription}
              </p>
            )}
            {actions && (
              <div className="mt-7 flex flex-wrap justify-center gap-3 md:justify-start">{actions}</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default PublicPageHeader;
