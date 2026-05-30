import { Link, useLocation } from "react-router-dom";
import { useState } from "react";
import { ArrowRight, Flame, LogIn, Menu, X } from "lucide-react";

const NAV_LINKS: ReadonlyArray<{ label: string; to: string }> = [
  { label: "For stores", to: "/for-stores" },
  { label: "How it works", to: "/how-it-works" },
  { label: "Features", to: "/features" },
  { label: "Contact", to: "/contact" },
  { label: "Support", to: "/support" },
];

export function PublicHeader() {
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const pathname = location.pathname;
  const isActive = (to: string) => pathname === to;
  const desktopLinkClass = (to: string) =>
    isActive(to)
      ? "rounded-full bg-primary/14 px-3 py-2 text-foreground ring-1 ring-primary/25 transition-colors"
      : "rounded-full px-3 py-2 transition-colors hover:bg-foreground/10 hover:text-foreground";
  const mobileLinkClass = (to: string) =>
    isActive(to)
      ? "flex items-center justify-between rounded-lg border border-primary/35 bg-primary/14 px-3 py-2.5 font-medium text-foreground shadow-[inset_0_1px_0_hsl(var(--primary-foreground)/0.12)]"
      : "block rounded-lg px-3 py-2.5 transition-colors hover:bg-foreground/10 hover:text-foreground";

  return (
    <header className="fixed top-0 z-40 w-full px-3 pt-3 md:sticky">
      <div className="container public-header-shell flex h-16 items-center gap-4 rounded-2xl px-4 md:gap-6 md:px-5">
        <Link
          to="/"
          className="flex items-center gap-2 rounded-md font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="NubeRush home"
        >
          <span className="premium-action inline-flex h-9 w-9 items-center justify-center rounded-xl text-primary-foreground">
            <Flame className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="text-base">NubeRush</span>
        </Link>

        <nav
          aria-label="Public site navigation"
          className="hidden md:flex items-center gap-1 rounded-full border border-foreground/10 bg-background/30 p-1 text-sm text-muted-foreground"
        >
          {NAV_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isActive(item.to) ? "page" : undefined}
              className={desktopLinkClass(item.to)}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link
            to="/login"
            aria-current={isActive("/login") ? "page" : undefined}
            className={`hidden h-10 items-center justify-center gap-2 rounded-full px-4 text-sm font-medium text-foreground transition-colors hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:inline-flex ${
              isActive("/login") ? "bg-primary/14 ring-1 ring-primary/25" : ""
            }`}
          >
            <LogIn className="h-4 w-4" aria-hidden="true" />
            Sign in
          </Link>
          <Link
            to="/request-demo"
            aria-current={isActive("/request-demo") ? "page" : undefined}
            className="premium-action hidden h-10 items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:inline-flex"
          >
            Request demo
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <button
            type="button"
            onClick={() => setIsMenuOpen((current) => !current)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-foreground/10 bg-foreground/10 text-foreground transition-colors hover:bg-foreground/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background md:hidden"
            aria-label="Toggle public navigation"
            aria-controls="public-mobile-navigation"
            aria-expanded={isMenuOpen}
          >
            {isMenuOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <nav
        id="public-mobile-navigation"
        aria-label="Public site navigation (mobile)"
        className={`md:hidden container overflow-hidden px-0 transition-all duration-300 ${
          isMenuOpen ? "max-h-96 pt-2 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <ul className="public-mobile-menu-panel grid gap-1.5 rounded-2xl p-2 text-sm text-muted-foreground">
          {NAV_LINKS.map((item) => (
            <li key={item.to}>
              <Link
                to={item.to}
                onClick={() => setIsMenuOpen(false)}
                aria-current={isActive(item.to) ? "page" : undefined}
                className={mobileLinkClass(item.to)}
              >
                {item.label}
                {isActive(item.to) && (
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                )}
              </Link>
            </li>
          ))}
          <li>
            <Link
              to="/login"
              onClick={() => setIsMenuOpen(false)}
              aria-current={isActive("/login") ? "page" : undefined}
              className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-foreground transition-colors hover:bg-foreground/10 ${
                isActive("/login")
                  ? "border border-primary/35 bg-primary/14 font-medium ring-1 ring-primary/20"
                  : ""
              }`}
            >
              <LogIn className="h-4 w-4" aria-hidden="true" />
              Sign in
            </Link>
          </li>
          <li className="sm:hidden">
            <Link
              to="/request-demo"
              onClick={() => setIsMenuOpen(false)}
              className="premium-action mt-1 flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 font-semibold text-primary-foreground"
            >
              Request demo
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}

export default PublicHeader;
