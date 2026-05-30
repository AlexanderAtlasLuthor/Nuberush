import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PublicSectionProps {
  eyebrow?: string;
  title?: string;
  description?: string;
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
  description,
  children,
  className,
  tone = "default",
  ariaLabel,
}: PublicSectionProps) {
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
        {(eyebrow || title || description) && (
          <div className="max-w-3xl">
            {eyebrow && (
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground md:text-4xl">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-3 text-base leading-relaxed text-foreground/64">
                {description}
              </p>
            )}
          </div>
        )}
        {children && (
          <div className={cn(eyebrow || title || description ? "mt-10" : undefined)}>
            {children}
          </div>
        )}
      </div>
    </section>
  );
}

export default PublicSection;
