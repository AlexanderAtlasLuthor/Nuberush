import { Link } from "react-router-dom";
import { ArrowUpRight, Mail } from "lucide-react";

import { BrandMark } from "@/components/common/brand-mark";

const PUBLIC_LINKS: ReadonlyArray<{ label: string; to: string }> = [
  { label: "Home", to: "/" },
  { label: "For stores", to: "/for-stores" },
  { label: "How it works", to: "/how-it-works" },
  { label: "Features", to: "/features" },
  { label: "Contact", to: "/contact" },
  { label: "Request demo", to: "/request-demo" },
  { label: "Support", to: "/support" },
];

const LEGAL_LINKS: ReadonlyArray<{ label: string; to: string }> = [
  { label: "Legal hub", to: "/legal" },
  { label: "Terms", to: "/legal/terms" },
  { label: "Privacy", to: "/legal/privacy" },
  { label: "Merchant Agreement", to: "/legal/merchant-agreement" },
  { label: "Acceptable Use", to: "/legal/acceptable-use" },
  { label: "Cookies", to: "/legal/cookies" },
];

export function PublicFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-foreground/10 bg-transparent">
      <div className="container py-10 md:py-12">
        <div className="grid gap-10 md:grid-cols-4">
          <div className="premium-glass-soft rounded-lg p-5 md:col-span-1">
            <Link
              to="/"
              className="flex items-center gap-2 font-semibold tracking-tight"
              aria-label="NubeRush home"
            >
              <BrandMark className="h-9 w-9" />
              <span>NubeRush</span>
            </Link>
            <p className="mt-4 text-sm leading-relaxed text-foreground/62">
              An operating platform for regulated local commerce. Tools for
              products, inventory, orders, compliance, and audit visibility.
            </p>
          </div>

          <nav
            aria-label="Public links"
            className="premium-glass-soft rounded-lg p-5 md:col-span-1"
          >
            <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
              Platform
            </h2>
            <ul className="mt-4 grid grid-cols-2 gap-2 text-sm md:block md:space-y-2">
              {PUBLIC_LINKS.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="flex items-center justify-between rounded-lg border border-foreground/8 bg-foreground/[0.04] px-3 py-2 text-foreground/78 transition-colors hover:border-primary/30 hover:bg-foreground/10 hover:text-foreground md:border-0 md:bg-transparent md:px-0 md:py-0"
                  >
                    <span>{item.label}</span>
                    <ArrowUpRight
                      className="h-3.5 w-3.5 text-primary/80 md:hidden"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
              <li>
                <Link
                  to="/login"
                  className="flex items-center justify-between rounded-lg border border-foreground/8 bg-foreground/[0.04] px-3 py-2 text-foreground/78 transition-colors hover:border-primary/30 hover:bg-foreground/10 hover:text-foreground md:border-0 md:bg-transparent md:px-0 md:py-0"
                >
                  <span>Sign in</span>
                  <ArrowUpRight
                    className="h-3.5 w-3.5 text-primary/80 md:hidden"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            </ul>
          </nav>

          <nav
            aria-label="Legal"
            className="premium-glass-soft rounded-lg p-5 md:col-span-1"
          >
            <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
              Legal
            </h2>
            <ul className="mt-4 grid gap-2 text-sm">
              {LEGAL_LINKS.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="flex items-center justify-between rounded-lg border border-foreground/8 bg-foreground/[0.04] px-3 py-2 text-foreground/78 transition-colors hover:border-primary/30 hover:bg-foreground/10 hover:text-foreground md:border-0 md:bg-transparent md:px-0 md:py-0"
                  >
                    <span>{item.label}</span>
                    <ArrowUpRight
                      className="h-3.5 w-3.5 text-primary/80 md:hidden"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="premium-glass-soft rounded-lg p-5 md:col-span-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
              Contact
            </h2>
            <p className="mt-4 text-sm text-foreground/62">
              Operated by NubeRush.
            </p>
            <p className="mt-2 text-sm">
              <a
                href="mailto:info@nuberush.com"
                className="inline-flex items-center gap-2 rounded-lg border border-foreground/8 bg-foreground/[0.04] px-3 py-2 text-foreground transition-colors hover:border-primary/30 hover:bg-foreground/10 hover:text-primary"
              >
                <Mail className="h-4 w-4 text-primary" aria-hidden="true" />
                info@nuberush.com
              </a>
            </p>
          </div>
        </div>

        <div className="premium-glass-soft mt-6 flex flex-col gap-2 rounded-lg px-4 py-4 text-xs text-foreground/58 sm:flex-row sm:items-center sm:justify-between md:mt-8">
          <p>© {year} NubeRush. All rights reserved.</p>
          <p>Built in South Florida for regulated local commerce.</p>
        </div>
      </div>
    </footer>
  );
}

export default PublicFooter;
