// F2.21.7 — SPA-level metadata for every public route.
//
// Each entry pairs a unique <title> and meta description with a
// public route. No SSR, no prerender, no sitemap, no JSON-LD, no OG
// image generation — only client-side document.title + meta updates
// applied through `PublicPageMeta`.
//
// Descriptions must stay truthful: no guaranteed compliance, no
// legally approved / certified compliant / instant approval claims,
// no payment / checkout / driver promises, no positive self-serve
// signup claims. Where the platform reality requires a disclaimer
// (self-serve signup), descriptions phrase it as the negation.

export interface PublicPageMetaEntry {
  title: string;
  description: string;
}

export const PUBLIC_PAGE_META = {
  "/": {
    title:
      "NubeRush — Operating Platform for Regulated Local Commerce",
    description:
      "NubeRush gives stores a single operating workspace for products, inventory, orders, compliance visibility, and audit history, with platform oversight for admins.",
  },
  "/for-stores": {
    title: "For Stores — NubeRush",
    description:
      "How NubeRush helps stores run product, inventory, order, and compliance-aware operations with operational visibility and audit-backed activity.",
  },
  "/how-it-works": {
    title: "How NubeRush Works",
    description:
      "From first conversation to operating on the platform — request a demo, set up store operations, organize products and inventory, and use platform oversight.",
  },
  "/features": {
    title: "NubeRush Features",
    description:
      "Capabilities NubeRush ships today across store operations, product oversight, inventory visibility, order operations, compliance visibility, audit, and admin oversight.",
  },
  "/contact": {
    title: "Contact NubeRush",
    description:
      "Reach the NubeRush team by email for general inquiries, merchant demo requests, support direction, and partnership conversations.",
  },
  "/request-demo": {
    title: "Apply to Sell on NubeRush",
    description:
      "Apply to open your store on NubeRush. The team reviews every application and provisions your store once approved. Self-serve signup is not available yet.",
  },
  "/support": {
    title: "NubeRush Support",
    description:
      "Starting points for stores, operators, and partners. Support flows through email and operator contact channels — no public ticketing system today.",
  },
  "/legal": {
    title: "Legal Documents — NubeRush",
    description:
      "Index of NubeRush legal and trust documents. Every document is an operational draft pending review by qualified legal counsel.",
  },
  "/legal/terms": {
    title: "Terms of Service — NubeRush",
    description:
      "Draft Terms of Service covering website use, account access, platform availability, prohibited use, and disclaimers. Pending legal review.",
  },
  "/legal/privacy": {
    title: "Privacy Policy — NubeRush",
    description:
      "Draft Privacy Policy describing what information NubeRush collects, how it is used, and the choices users have. Pending legal review.",
  },
  "/legal/merchant-agreement": {
    title: "Merchant Agreement — NubeRush",
    description:
      "Draft Merchant Agreement covering responsibilities for stores on NubeRush, including product accuracy, age-restricted handling, and compliance. Pending legal review.",
  },
  "/legal/acceptable-use": {
    title: "Acceptable Use Policy — NubeRush",
    description:
      "Draft Acceptable Use Policy outlining what is and is not permitted on the NubeRush platform, including misuse and enforcement. Pending legal review.",
  },
  "/legal/cookies": {
    title: "Cookie Policy — NubeRush",
    description:
      "Draft Cookie Policy explaining cookies the NubeRush website and platform may use, and how to manage them. Pending legal review.",
  },
} as const satisfies Record<string, PublicPageMetaEntry>;

export type PublicMetaPath = keyof typeof PUBLIC_PAGE_META;

// Fallback meta returned by getPageMeta() when a non-public path is
// requested (e.g. /login). Resolves to the home-page meta so the
// helper never produces an empty <title>.
export const DEFAULT_PAGE_META: PublicPageMetaEntry = PUBLIC_PAGE_META["/"];

/**
 * Pure lookup for tests + non-React contexts. Returns the home-page
 * meta entry for unknown paths so callers always get a usable title
 * and description.
 */
export function getPageMeta(path: string): PublicPageMetaEntry {
  return (
    (PUBLIC_PAGE_META as Record<string, PublicPageMetaEntry>)[path] ??
    DEFAULT_PAGE_META
  );
}
