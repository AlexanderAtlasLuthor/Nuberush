import { Link } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  ClipboardCheck,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

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
      className="relative w-full overflow-hidden border-b border-foreground/10"
    >
      <div className="absolute inset-x-0 top-0 -z-10 h-full bg-[radial-gradient(circle_at_50%_8%,hsl(var(--primary)/0.22),transparent_34rem)]" />
      <div className="container relative grid min-h-[calc(100svh-5.75rem)] content-center pb-14 pt-28 text-center md:pb-20 md:pt-24">
        <div className="pointer-events-none absolute left-1/2 top-10 -z-10 hidden w-[min(920px,82vw)] -translate-x-1/2 md:block">
          <div className="premium-glass-soft h-80 rotate-[-2deg] rounded-[2rem] p-4 opacity-70">
            <div className="grid h-full grid-cols-[1fr_1.3fr] gap-4">
              <div className="space-y-3 rounded-3xl bg-background/28 p-4">
                <div className="h-3 w-24 rounded-full bg-primary/50" />
                <div className="h-14 rounded-2xl bg-foreground/10" />
                <div className="h-14 rounded-2xl bg-foreground/10" />
                <div className="h-14 rounded-2xl bg-foreground/10" />
              </div>
              <div className="rounded-3xl bg-background/32 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="h-3 w-28 rounded-full bg-foreground/18" />
                  <div className="h-8 w-20 rounded-full bg-primary/35" />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="h-24 rounded-2xl bg-primary/18" />
                  <div className="h-24 rounded-2xl bg-cyan-400/12" />
                  <div className="h-24 rounded-2xl bg-foreground/10" />
                </div>
                <div className="mt-4 h-24 rounded-2xl bg-foreground/10" />
              </div>
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-4xl">
          {eyebrow && (
            <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {eyebrow}
            </p>
          )}
          <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight text-foreground md:text-6xl lg:text-7xl">
            {headline}
          </h1>
          {subhead && (
            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-foreground/68 md:text-lg">
              {subhead}
            </p>
          )}
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              to={primary.to}
              className="premium-action inline-flex h-11 items-center justify-center gap-2 rounded-full px-6 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {primary.label}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            {secondary && (
              <Link
                to={secondary.to}
                className="inline-flex h-11 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-6 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {secondary.label}
              </Link>
            )}
          </div>
        </div>

        <div className="mx-auto mt-10 grid w-full max-w-3xl gap-3 sm:grid-cols-3">
          {[
            { label: "Products", icon: Boxes },
            { label: "Orders", icon: ClipboardCheck },
            { label: "Compliance", icon: ShieldCheck },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="premium-glass-soft rounded-2xl px-4 py-3 text-sm font-medium text-foreground/82"
              >
                <span className="inline-flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  {item.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default PublicHero;
