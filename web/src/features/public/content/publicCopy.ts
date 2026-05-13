import {
  BadgeCheck,
  Boxes,
  Building2,
  ClipboardList,
  Eye,
  FileWarning,
  Gauge,
  LayoutDashboard,
  RadioTower,
  ShieldCheck,
  ShoppingBag,
  Workflow,
  type LucideIcon,
} from "lucide-react";

// Structured public-site copy. Page components consume these arrays so
// copy lives in one auditable location. Nothing in this file is a
// runtime/UI primitive — only data. No fake stats, fake testimonials,
// fake partner logos, or guaranteed-compliance claims (see contract §6).

export interface TrustPoint {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const TRUST_POINTS: ReadonlyArray<TrustPoint> = [
  {
    title: "Operational visibility",
    body: "See product, inventory, and order activity from a single workspace.",
    icon: Eye,
  },
  {
    title: "Compliance-aware workflows",
    body: "Surface compliance status alongside the operations that depend on it.",
    icon: ShieldCheck,
  },
  {
    title: "Audit-backed activity",
    body: "Important operational changes are recorded for accountable review.",
    icon: BadgeCheck,
  },
  {
    title: "Platform oversight",
    body: "Admins keep visibility across stores, users, and operational signals.",
    icon: LayoutDashboard,
  },
];

export interface Problem {
  title: string;
  body: string;
}

export const PROBLEMS: ReadonlyArray<Problem> = [
  {
    title: "Product data scattered across tools",
    body: "Stores juggle product info between spreadsheets, point-of-sale tools, and chat threads.",
  },
  {
    title: "Inventory and orders disconnected",
    body: "Stock levels and order activity drift apart, making the day harder to operate.",
  },
  {
    title: "Compliance visibility is hard to monitor",
    body: "Restricted or banned product signals get lost across systems and people.",
  },
  {
    title: "Manual operations slow teams down",
    body: "Owners and managers spend time reconciling state instead of running the store.",
  },
  {
    title: "Platform operators need centralized oversight",
    body: "Cross-store visibility — products, inventory, orders, compliance — is rarely in one place.",
  },
];

export interface SolutionPillar {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const SOLUTION_PILLARS: ReadonlyArray<SolutionPillar> = [
  {
    title: "Store workspace",
    body: "A focused operator surface for store owners, managers, and staff to run the day.",
    icon: Building2,
  },
  {
    title: "Admin console",
    body: "Platform-level visibility across stores, users, and operational signals.",
    icon: LayoutDashboard,
  },
  {
    title: "Connected operations",
    body: "Products, inventory, orders, compliance, and audit are part of one operating model.",
    icon: Workflow,
  },
];

export interface FeatureCard {
  title: string;
  body: string;
  icon: LucideIcon;
}

// Eight feature cards locked by the F2.21.2 contract section §5.
export const FEATURES: ReadonlyArray<FeatureCard> = [
  {
    title: "Product oversight",
    body: "Organize product information and status in one operational workspace.",
    icon: ShoppingBag,
  },
  {
    title: "Inventory visibility",
    body: "Keep stock and movement signals visible to store teams.",
    icon: Boxes,
  },
  {
    title: "Order operations",
    body: "Track operational order flow from the store workspace.",
    icon: ClipboardList,
  },
  {
    title: "Compliance visibility",
    body: "Surface product compliance status and review needs.",
    icon: ShieldCheck,
  },
  {
    title: "Audit trail",
    body: "Keep important operational activity traceable.",
    icon: BadgeCheck,
  },
  {
    title: "Admin console",
    body: "Give platform operators visibility across stores and workflows.",
    icon: LayoutDashboard,
  },
  {
    title: "Store workspace",
    body: "Give merchants a focused area for daily operations.",
    icon: Building2,
  },
  {
    title: "Operations alerts",
    body: "Highlight issues before they become operational chaos.",
    icon: RadioTower,
  },
];

export interface HowItWorksStep {
  step: string;
  title: string;
  body: string;
}

export const HOW_IT_WORKS_STEPS: ReadonlyArray<HowItWorksStep> = [
  {
    step: "1",
    title: "Request a demo",
    body: "Reach the NubeRush team to discuss your store and what you need.",
  },
  {
    step: "2",
    title: "Set up store operations",
    body: "Your store profile, users, and operator preferences are configured by the team.",
  },
  {
    step: "3",
    title: "Organize products and inventory",
    body: "Bring your catalog and stock into one operating workspace.",
  },
  {
    step: "4",
    title: "Monitor orders and compliance visibility",
    body: "Track order flow and surface product compliance signals as you operate.",
  },
  {
    step: "5",
    title: "Use platform oversight and audit history",
    body: "Lean on admin oversight and operational audit when you need traceability.",
  },
];

export interface OperationsArea {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const OPERATIONS_PREVIEW_AREAS: ReadonlyArray<OperationsArea> = [
  {
    title: "Products",
    body: "Catalog, variants, and compliance state in one operating view.",
    icon: ShoppingBag,
  },
  {
    title: "Inventory",
    body: "Stock levels per store with movement history.",
    icon: Boxes,
  },
  {
    title: "Orders",
    body: "Order list, detail, and audit history for store operators.",
    icon: ClipboardList,
  },
  {
    title: "Compliance",
    body: "Restricted and banned product visibility surfaced on the product itself.",
    icon: FileWarning,
  },
  {
    title: "Audit",
    body: "Store-scoped and platform-scoped audit feeds for operator decisions.",
    icon: ShieldCheck,
  },
  {
    title: "Admin oversight",
    body: "Cross-store visibility for platform operators across the surface.",
    icon: Gauge,
  },
];

export interface FaqItem {
  question: string;
  answer: string;
}

export const FAQ_ITEMS: ReadonlyArray<FaqItem> = [
  {
    question: "What is NubeRush?",
    answer:
      "NubeRush is an operating platform for regulated local commerce. It gives store owners and operators a single workspace for products, inventory, orders, compliance visibility, and audit history, plus an admin console for platform oversight.",
  },
  {
    question: "Who is NubeRush for?",
    answer:
      "Local retail operators who need control, oversight, and traceability — typically stores that handle regulated or age-restricted products and care about operational accountability.",
  },
  {
    question: "Is NubeRush only for smoke shops?",
    answer:
      "No. NubeRush is designed for regulated local commerce broadly. The platform supports stores where product status, operational visibility, and responsible oversight matter, beyond any single retail category.",
  },
  {
    question: "Can stores manage products?",
    answer:
      "Yes. The store workspace gives operators a focused surface to manage products, variants, and the operational signals that go with them.",
  },
  {
    question: "Does NubeRush handle compliance?",
    answer:
      "NubeRush provides compliance-aware tools and visibility — it surfaces product compliance status and review signals. Merchants remain responsible for understanding and following the laws that apply to their business. NubeRush does not provide legal advice or guarantee legal compliance.",
  },
  {
    question: "Can I request a demo?",
    answer:
      "Yes. Use the Request demo page to email the NubeRush team. Share your business, location, and what you'd like to discuss.",
  },
  {
    question: "Is self-serve signup available?",
    answer:
      "Self-serve signup is not available yet. Stores are activated by the NubeRush team after a conversation. Request a demo to start that conversation.",
  },
  {
    question: "Is NubeRush available outside South Florida?",
    answer:
      "NubeRush was built in South Florida, and availability is expanding. If your store is outside the area, request a demo and we'll discuss whether we can support your operation today.",
  },
];

// Hero, regulated-commerce framing, and CTA-band copy live as plain
// strings so HomePage stays declarative without scattering raw copy.

export const HERO_COPY = {
  eyebrow: "NubeRush",
  headline: "The operating platform for regulated local commerce.",
  subhead:
    "A single workspace for stores to run products, inventory, orders, compliance visibility, and audit history — with platform oversight for operators who need control and traceability.",
  primaryCta: { label: "Request demo", to: "/request-demo" },
  secondaryCta: { label: "See how it works", to: "/how-it-works" },
} as const;

export const REGULATED_COMMERCE_COPY = {
  title: "Built for regulated local commerce.",
  body: "NubeRush is designed for stores where product status, operational visibility, and responsible oversight matter. Compliance-aware workflows support visibility, but merchants remain responsible for understanding and following the laws that apply to their business. The platform does not provide legal advice or guarantee compliance.",
  highlights: [
    "Compliance state lives next to the product, not in a separate silo.",
    "Audit history records important operational activity for accountable review.",
    "Admin oversight gives platform operators cross-store visibility — no client-side aggregation.",
  ] as ReadonlyArray<string>,
} as const;

export const CTA_BAND_COPY = {
  title: "Talk to the NubeRush team.",
  description:
    "Request a demo for your store, or send a general inquiry. The team responds from team@fuenmayorindustries.com.",
  primary: { label: "Request demo", to: "/request-demo" },
  secondary: { label: "Contact us", to: "/contact" },
} as const;

// Visual layer used by the trust band to render the four pillars
// with consistent token-aligned styling.
export interface SectionHeading {
  eyebrow?: string;
  title: string;
  description?: string;
}

export const PROBLEM_SECTION: SectionHeading = {
  eyebrow: "What stores deal with",
  title: "The problems regulated stores actually face.",
  description:
    "The day-to-day pain isn't glamorous — it's scattered data, disconnected systems, and operational signals that go missing when they're most needed.",
};

export const SOLUTION_SECTION: SectionHeading = {
  eyebrow: "What NubeRush is",
  title: "Store operations in one workspace.",
  description:
    "NubeRush brings the operational surface together: a store workspace for daily operations, an admin console for platform oversight, and a model that connects products, inventory, orders, compliance, and audit.",
};

export const FEATURES_SECTION: SectionHeading = {
  eyebrow: "Features",
  title: "What the platform actually ships.",
  description:
    "Capabilities below map to real screens in the store and admin consoles — we don't list features we haven't built.",
};

export const HOW_IT_WORKS_SECTION: SectionHeading = {
  eyebrow: "How it works",
  title: "From first conversation to operating on the platform.",
  description:
    "Onboarding is hands-on. There is no self-serve signup queue.",
};

export const OPERATIONS_PREVIEW_SECTION: SectionHeading = {
  eyebrow: "Operations preview",
  title: "The operational areas NubeRush is organizing.",
  description:
    "Each area below is a real surface inside the store or admin console — not a future-tense promise.",
};

export const FAQ_SECTION: SectionHeading = {
  eyebrow: "FAQ",
  title: "Frequently asked questions.",
};

// ───────────────────────────────────────────────────────────────────
// F2.21.3 — Merchant Education Pages
//
// Structured content for /for-stores, /how-it-works, and /features.
// HomePage exports above stay unchanged: HOW_IT_WORKS_STEPS keeps its
// 5-step preview shape; HOW_IT_WORKS_DETAILED_STEPS below is the
// 8-step flow consumed by the dedicated /how-it-works page.
// ───────────────────────────────────────────────────────────────────

// /for-stores ───────────────────────────────────────────────────────

export const FOR_STORES_COPY = {
  eyebrow: "For stores",
  headline:
    "For stores that need operational clarity before chaos starts.",
  subhead:
    "NubeRush gives merchants a focused workspace for product, inventory, order, and compliance visibility — connected to platform oversight and audit history so the day stays under control.",
  primaryCta: { label: "Request demo", to: "/request-demo" },
  secondaryCta: { label: "See how it works", to: "/how-it-works" },
} as const;

export interface ForStoresSection {
  title: string;
  body: string;
  bullets: ReadonlyArray<string>;
  icon: LucideIcon;
}

export const FOR_STORES_SECTIONS: ReadonlyArray<ForStoresSection> = [
  {
    title: "Why stores use NubeRush",
    body: "Stores come to NubeRush when product data, inventory, orders, and compliance signals stop talking to each other. The platform brings those signals into one operating workspace.",
    bullets: [
      "Operational visibility across the day's work.",
      "Compliance status visible alongside the product, not in a silo.",
      "Audit history that backs operator decisions for accountable review.",
    ],
    icon: Eye,
  },
  {
    title: "Product operations",
    body: "Manage the product catalog from a single workspace — variants, status, and compliance state in one place.",
    bullets: [
      "Catalog editing with variants.",
      "Compliance state surfaced on the product itself.",
      "Updates land where operators already work.",
    ],
    icon: ShoppingBag,
  },
  {
    title: "Inventory visibility",
    body: "Keep stock levels and movement signals visible to store teams so the floor and the workspace stay in sync.",
    bullets: [
      "Stock levels per store with movement history.",
      "Low-stock visibility tied to the product.",
      "No fake cross-store aggregation in the frontend.",
    ],
    icon: Boxes,
  },
  {
    title: "Order oversight",
    body: "Track operational order flow from the store workspace — lifecycle, status, and audit trail in one view.",
    bullets: [
      "Order list, detail, and audit history.",
      "Status transitions handled in the operator surface.",
      "Store-scoped visibility for store users, platform-scoped for admins.",
    ],
    icon: ClipboardList,
  },
  {
    title: "Compliance-aware workflows",
    body: "Compliance state — restricted, banned, or under review — is part of the operating model. Operators see it where it matters.",
    bullets: [
      "Product compliance status visible alongside catalog.",
      "Audit log records compliance state changes.",
      "Merchants remain responsible for understanding and following the laws that apply to their business.",
    ],
    icon: ShieldCheck,
  },
  {
    title: "Admin/platform support",
    body: "Stores aren't alone on the platform. The NubeRush team provides hands-on onboarding, and platform admins keep cross-store visibility.",
    bullets: [
      "Manual onboarding led by the NubeRush team.",
      "Platform admin console for cross-store visibility.",
      "Operations alerts so issues surface before they escalate.",
    ],
    icon: LayoutDashboard,
  },
  {
    title: "Audit / traceability",
    body: "Important operational activity is recorded so operators, owners, and admins can review what happened and when.",
    bullets: [
      "Store-scoped audit feed for store teams.",
      "Platform-scoped audit feed for admins.",
      "Traceability for product, inventory, order, and compliance changes.",
    ],
    icon: BadgeCheck,
  },
];

export const FOR_STORES_SECTION_HEADING: SectionHeading = {
  eyebrow: "What stores get from NubeRush",
  title: "An operating workspace for regulated local retail.",
  description:
    "Each area below is part of the real platform — product, inventory, order, compliance, admin, and audit visibility for stores that need control.",
};

export const FOR_STORES_CTA_BAND = {
  title: "Bring your store onto NubeRush.",
  description:
    "Request a demo to start a conversation with the NubeRush team. Self-serve signup is not available yet.",
  primary: { label: "Request demo", to: "/request-demo" },
  secondary: { label: "Contact us", to: "/contact" },
} as const;

// /how-it-works ─────────────────────────────────────────────────────

export const HOW_IT_WORKS_COPY = {
  eyebrow: "How it works",
  headline: "From request to operating on the platform.",
  subhead:
    "Access to NubeRush starts with a conversation. Self-serve signup is not available yet — request a demo and the NubeRush team works through fit, setup, and onboarding with you.",
  primaryCta: { label: "Request demo", to: "/request-demo" },
  secondaryCta: { label: "For stores", to: "/for-stores" },
} as const;

export const HOW_IT_WORKS_DETAILED_STEPS: ReadonlyArray<HowItWorksStep> = [
  {
    step: "1",
    title: "Request a demo",
    body: "Reach the NubeRush team at team@fuenmayorindustries.com or via the Request demo page. Share your store, location, and what you'd like to discuss.",
  },
  {
    step: "2",
    title: "Confirm store fit and operating needs",
    body: "The team works with you to confirm whether NubeRush fits your store today, what onboarding looks like, and what operational areas you'll start with.",
  },
  {
    step: "3",
    title: "Set up store workspace",
    body: "Your store profile, users, and operator preferences are configured by the NubeRush team. Owners, managers, and staff get access tailored to their role.",
  },
  {
    step: "4",
    title: "Organize product catalog",
    body: "Bring your catalog into the platform with variants and product status. Compliance state is captured alongside each product, not in a separate system.",
  },
  {
    step: "5",
    title: "Connect inventory visibility",
    body: "Surface stock levels per store with movement history. Inventory and product status share the same operating model from day one.",
  },
  {
    step: "6",
    title: "Track order operations",
    body: "Use the store workspace to manage order lifecycle — list, detail, status transitions, and audit history — without bouncing between tools.",
  },
  {
    step: "7",
    title: "Monitor compliance visibility",
    body: "Restricted and banned product signals stay visible alongside the catalog. The platform surfaces signals; merchants remain responsible for understanding and following the laws that apply to their business.",
  },
  {
    step: "8",
    title: "Use admin oversight and audit history",
    body: "Lean on platform admin oversight for cross-store visibility and on audit history when you need to trace operator decisions for accountable review.",
  },
];

export const HOW_IT_WORKS_PAGE_SECTION: SectionHeading = {
  eyebrow: "The flow",
  title: "Eight steps from first conversation to operating.",
  description:
    "Onboarding is hands-on. The platform doesn't promise a fast-track path or a sign-up wizard — the goal is to get your store running well, not quickly.",
};

export const HOW_IT_WORKS_PRINCIPLES_SECTION: SectionHeading = {
  eyebrow: "What hands-on onboarding means",
  title: "How NubeRush works with stores in practice.",
};

export const HOW_IT_WORKS_PRINCIPLES: ReadonlyArray<string> = [
  "Self-serve signup is not available yet. Stores are onboarded by the NubeRush team.",
  "Stores should request a demo to begin a conversation with the team.",
  "NubeRush supports operational visibility. Merchants remain responsible for their own legal and compliance obligations.",
];

export const HOW_IT_WORKS_CTA_BAND = {
  title: "Start the conversation.",
  description:
    "Request a demo to begin. The team responds from team@fuenmayorindustries.com.",
  primary: { label: "Request demo", to: "/request-demo" },
  secondary: { label: "For stores", to: "/for-stores" },
} as const;

// /features ─────────────────────────────────────────────────────────

export const FEATURES_PAGE_COPY = {
  eyebrow: "Features",
  headline: "Capabilities for stores that need operational visibility.",
  subhead:
    "The platform groups capabilities by operating area — products and inventory, orders, compliance visibility, admin oversight, and audit. Each capability below maps to a real screen the platform ships.",
  primaryCta: { label: "Request demo", to: "/request-demo" },
  secondaryCta: { label: "See how it works", to: "/how-it-works" },
} as const;

export interface FeatureCapability {
  title: string;
  body: string;
}

export interface FeatureGroup {
  title: string;
  description: string;
  icon: LucideIcon;
  capabilities: ReadonlyArray<FeatureCapability>;
}

export const FEATURES_PAGE_GROUPS: ReadonlyArray<FeatureGroup> = [
  {
    title: "Store operations",
    description:
      "A focused workspace for store owners, managers, and staff to run the day.",
    icon: Building2,
    capabilities: [
      {
        title: "Store workspace",
        body: "An operator surface tailored to the daily store experience — products, inventory, orders, compliance, and audit in one navigation.",
      },
    ],
  },
  {
    title: "Product & inventory",
    description:
      "Catalog data and stock signals together in one operating view.",
    icon: ShoppingBag,
    capabilities: [
      {
        title: "Product oversight",
        body: "Organize product information and status in one operational workspace.",
      },
      {
        title: "Inventory visibility",
        body: "Keep stock and movement signals visible to store teams.",
      },
    ],
  },
  {
    title: "Orders",
    description:
      "Operational order flow from inside the store workspace, with audit history.",
    icon: ClipboardList,
    capabilities: [
      {
        title: "Order operations",
        body: "Track operational order flow from the store workspace.",
      },
    ],
  },
  {
    title: "Compliance visibility",
    description:
      "Compliance state surfaced alongside the catalog, not in a silo.",
    icon: ShieldCheck,
    capabilities: [
      {
        title: "Compliance visibility",
        body: "Surface product compliance status and review needs so they are visible alongside daily operations.",
      },
    ],
  },
  {
    title: "Admin oversight",
    description:
      "Platform-level visibility for operators across stores and operational signals.",
    icon: LayoutDashboard,
    capabilities: [
      {
        title: "Admin console",
        body: "Give platform operators visibility across stores and workflows.",
      },
      {
        title: "Operations alerts",
        body: "Highlight issues before they become operational chaos.",
      },
    ],
  },
  {
    title: "Audit & visibility",
    description:
      "Important operational activity recorded for accountable review.",
    icon: BadgeCheck,
    capabilities: [
      {
        title: "Audit trail",
        body: "Keep important operational activity traceable across store and platform surfaces.",
      },
    ],
  },
];

export const FEATURES_PAGE_CTA_BAND = {
  title: "Want a closer look?",
  description:
    "Request a walkthrough of the operator surface from the NubeRush team.",
  primary: { label: "Request demo", to: "/request-demo" },
  secondary: { label: "See how it works", to: "/how-it-works" },
} as const;

// ───────────────────────────────────────────────────────────────────
// F2.21.4 — Contact + Request Demo
//
// Structured content for /contact and /request-demo. Both pages
// rely on an honest email CTA only — no form, no fake success state,
// no POST endpoint. The locked business email is also defined here
// so page components don't scatter raw strings.
// ───────────────────────────────────────────────────────────────────

export const BUSINESS_EMAIL = "team@fuenmayorindustries.com";
export const BUSINESS_EMAIL_MAILTO = `mailto:${BUSINESS_EMAIL}`;

// /contact ──────────────────────────────────────────────────────────

export const CONTACT_PAGE_COPY = {
  eyebrow: "Contact",
  headline: "Contact NubeRush.",
  subhead:
    "Reach the NubeRush team by email for general inquiries, merchant demo requests, support direction, and partnership conversations. We don't collect contact details through a form on this site.",
  primaryCta: {
    label: "Email us",
    href: BUSINESS_EMAIL_MAILTO,
    external: true,
  },
  secondaryCta: { label: "Request demo", to: "/request-demo" },
} as const;

export interface SectionCard {
  title: string;
  body: string;
}

export const CONTACT_SECTIONS: ReadonlyArray<SectionCard> = [
  {
    title: "General contact",
    body: "For most inquiries, email the NubeRush team. Share who you are, what you need, and the best way to reach you. Replies come from the NubeRush team — response time varies and is not guaranteed.",
  },
  {
    title: "Merchant demo inquiries",
    body: "Looking to evaluate the platform for your store? The dedicated Request demo page covers what to include and what to expect.",
  },
  {
    title: "Support direction",
    body: "If you operate a store on NubeRush today and need help, reach out to your usual NubeRush operations contact or email the team. The platform does not run a public ticketing system or always-on helpdesk.",
  },
  {
    title: "Business/partnership inquiries",
    body: "Vendor, integration, or partnership outreach is welcome. Email the team and describe what you'd like to explore.",
  },
];

export const CONTACT_EMAIL_CHECKLIST: ReadonlyArray<string> = [
  "Your name",
  "Business name",
  "City and state",
  "Store type or business type",
  "Number of locations",
  "What you need help with",
  "Best way to reach you",
];

export const CONTACT_CHECKLIST_SECTION: SectionHeading = {
  eyebrow: "What to include in your email",
  title: "Helpful details for routing your message.",
  description:
    "Including the details below helps the team understand your situation and reply with something useful.",
};

export const CONTACT_CTA_SECTION: SectionHeading = {
  eyebrow: "Start the conversation",
  title: "Ready to email the team?",
  description:
    "Send a message any time. Replies come from the same address.",
};

// /request-demo ─────────────────────────────────────────────────────

export const REQUEST_DEMO_PAGE_COPY = {
  eyebrow: "Request demo",
  headline: "Request a demo of NubeRush.",
  subhead:
    "Demos start with an email to the NubeRush team. The team works through fit, setup, and onboarding with you — there is no self-serve signup yet.",
  primaryCta: {
    label: "Email the team",
    href: BUSINESS_EMAIL_MAILTO,
    external: true,
  },
  secondaryCta: { label: "See how it works", to: "/how-it-works" },
} as const;

export const REQUEST_DEMO_SECTIONS: ReadonlyArray<SectionCard> = [
  {
    title: "Who should request a demo",
    body: "Store owners, managers, and operators who want product, inventory, order, and compliance visibility in one operating workspace. Stores serving regulated local commerce are the primary fit today.",
  },
  {
    title: "What happens after you reach out",
    body: "The NubeRush team reviews your message and replies from the business address. Response time is not guaranteed and varies by request. If we're a fit, the team proposes a conversation to walk through your operation and what onboarding would look like.",
  },
  {
    title: "What to include in your demo request",
    body: "Sharing the details below helps the team route your request and prepare a useful conversation.",
  },
  {
    title: "What NubeRush can help you evaluate",
    body: "A walkthrough covers the actual operator surface — store workspace, product oversight, inventory visibility, order operations, compliance visibility, audit history, and admin oversight. The team will tailor the conversation to your operation.",
  },
  {
    title: "Current access model",
    body: "Onboarding is hands-on. Stores are activated by the NubeRush team after a conversation.",
  },
];

export const REQUEST_DEMO_CHECKLIST: ReadonlyArray<string> = [
  "Business name",
  "City and state",
  "Store type",
  "Number of locations",
  "Current operational pain",
  "Product/inventory/order needs",
  "Compliance visibility needs",
  "Contact information",
];

export const REQUEST_DEMO_ACCESS_MODEL: ReadonlyArray<string> = [
  "Self-serve signup is not available yet.",
  "Demo requests begin by contacting the NubeRush team at team@fuenmayorindustries.com.",
  "Store access is handled by the NubeRush team after fit and operating needs are discussed.",
];

export const REQUEST_DEMO_CHECKLIST_SECTION: SectionHeading = {
  eyebrow: "What to include",
  title: "Details that help the team prepare your demo.",
};

export const REQUEST_DEMO_ACCESS_SECTION: SectionHeading = {
  eyebrow: "Current access model",
  title: "How stores get onto NubeRush today.",
};

export const REQUEST_DEMO_CTA_SECTION: SectionHeading = {
  eyebrow: "Start the conversation",
  title: "Email the team to begin.",
  description:
    "Replies come from the same address. Response time varies by request.",
};
