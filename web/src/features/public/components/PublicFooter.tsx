import { Link } from "react-router-dom";
import { Flame } from "lucide-react";

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
    <footer className="border-t border-border bg-background">
      <div className="container py-12">
        <div className="grid gap-10 md:grid-cols-4">
          <div className="md:col-span-1">
            <Link
              to="/"
              className="flex items-center gap-2 font-semibold tracking-tight"
              aria-label="NubeRush home"
            >
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Flame className="h-4 w-4" aria-hidden="true" />
              </span>
              <span>NubeRush</span>
            </Link>
            <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
              An operating platform for regulated local commerce. Tools for
              products, inventory, orders, compliance, and audit visibility.
            </p>
          </div>

          <nav aria-label="Public links" className="md:col-span-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Platform
            </h2>
            <ul className="mt-4 space-y-2 text-sm">
              {PUBLIC_LINKS.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="text-foreground/80 hover:text-foreground transition-colors"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
              <li>
                <Link
                  to="/login"
                  className="text-foreground/80 hover:text-foreground transition-colors"
                >
                  Sign in
                </Link>
              </li>
            </ul>
          </nav>

          <nav aria-label="Legal" className="md:col-span-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Legal
            </h2>
            <ul className="mt-4 space-y-2 text-sm">
              {LEGAL_LINKS.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="text-foreground/80 hover:text-foreground transition-colors"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="md:col-span-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Contact
            </h2>
            <p className="mt-4 text-sm text-muted-foreground">
              Operated by Fuenmayor Industries.
            </p>
            <p className="mt-2 text-sm">
              <a
                href="mailto:team@fuenmayorindustries.com"
                className="text-foreground hover:text-primary transition-colors"
              >
                team@fuenmayorindustries.com
              </a>
            </p>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-muted-foreground">
          <p>© {year} NubeRush. All rights reserved.</p>
          <p>Built in South Florida for regulated local commerce.</p>
        </div>
      </div>
    </footer>
  );
}

export default PublicFooter;
