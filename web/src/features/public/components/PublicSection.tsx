import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useMobileCopy } from "./useMobileCopy";

interface PublicSectionProps {
  eyebrow?: string;
  title?: string;
  mobileTitle?: string;
  description?: string;
  mobileDescription?: string;
  children?: ReactNode;
  className?: string;
  /**
   * Optional visual tone for the section background. Defaults to the
   * page background; "muted" uses the card token for subtle alternation.
   */
  tone?: "default" | "muted";
  /** Optional aria-labelledby/aria-label override for the section. */
  ariaLabel?: string;
}

export function PublicSection({
  eyebrow,
  title,
  mobileTitle,
  description,
  mobileDescription,
  children,
  className,
  tone = "default",
  ariaLabel,
}: PublicSectionProps) {
  const isMobileCopy = useMobileCopy();
  const displayTitle = isMobileCopy && mobileTitle ? mobileTitle : title;
  const displayDescription =
    isMobileCopy && mobileDescription ? mobileDescription : description;
  const toneClass =
    tone === "muted"
      ? "bg-foreground/[0.025] backdrop-blur-sm"
      : "bg-transparent";

  return (
    <section
      aria-label={ariaLabel}
      className={cn("w-full py-14 md:py-20", toneClass, className)}
    >
      <div className="container">
        {(eyebrow || displayTitle || displayDescription) && (
          <div className="mx-auto max-w-3xl text-center md:mx-0 md:text-left">
            {eyebrow && (
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {eyebrow}
              </p>
            )}
            {displayTitle && (
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground md:text-4xl">
                {displayTitle}
              </h2>
            )}
            {displayDescription && (
              <p className="mt-3 text-base leading-relaxed text-foreground/64">
                {displayDescription}
              </p>
            )}
          </div>
        )}
        {children && (
          <div
            className={cn(
              eyebrow || displayTitle || displayDescription ? "mt-10" : undefined,
            )}
          >
            {children}
          </div>
        )}
      </div>
    </section>
  );
}

export default PublicSection;
