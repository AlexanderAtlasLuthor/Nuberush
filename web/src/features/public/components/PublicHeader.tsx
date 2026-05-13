import { Link } from "react-router-dom";
import { Flame } from "lucide-react";

const NAV_LINKS: ReadonlyArray<{ label: string; to: string }> = [
  { label: "For stores", to: "/for-stores" },
  { label: "How it works", to: "/how-it-works" },
  { label: "Features", to: "/features" },
  { label: "Contact", to: "/contact" },
  { label: "Support", to: "/support" },
];

export function PublicHeader() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="container flex h-16 items-center gap-6">
        <Link
          to="/"
          className="flex items-center gap-2 font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-md"
          aria-label="NubeRush home"
        >
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Flame className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>NubeRush</span>
        </Link>

        <nav
          aria-label="Public site navigation"
          className="hidden md:flex items-center gap-5 text-sm text-muted-foreground"
        >
          {NAV_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="hover:text-foreground transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link
            to="/login"
            className="hidden sm:inline-flex items-center justify-center h-9 px-3 rounded-md text-sm font-medium text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Sign in
          </Link>
          <Link
            to="/request-demo"
            className="inline-flex items-center justify-center h-9 px-4 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Request demo
          </Link>
        </div>
      </div>

      <nav
        aria-label="Public site navigation (mobile)"
        className="md:hidden border-t border-border"
      >
        <ul className="container flex flex-wrap gap-x-4 gap-y-1 py-2 text-sm text-muted-foreground">
          {NAV_LINKS.map((item) => (
            <li key={item.to}>
              <Link to={item.to} className="hover:text-foreground transition-colors">
                {item.label}
              </Link>
            </li>
          ))}
          <li className="sm:hidden">
            <Link to="/login" className="hover:text-foreground transition-colors">
              Sign in
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}

export default PublicHeader;
