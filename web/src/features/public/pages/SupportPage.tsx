import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { useMobileCopy } from "../components/useMobileCopy";

// F2.21.6 hardening: SupportPage is intentionally lightweight — a
// formal help center belongs to a later phase — but it must not be a
// dead end. Every topic card carries a clear next step (Link or
// mailto), and a "More resources" section cross-links to the main
// public surfaces so visitors arriving at /support always have
// somewhere to go.

interface SupportTopic {
  title: string;
  body: string;
  cta: {
    label: string;
    to?: string;
    mailto?: string;
  };
}

const TOPICS: ReadonlyArray<SupportTopic> = [
  {
    title: "I run a store on NubeRush and need help",
    body: "Reach out to your usual NubeRush operations contact, or email the team. Store users keep using their existing sign-in.",
    cta: {
      label: "Email the team",
      mailto: "mailto:info@nuberush.com",
    },
  },
  {
    title: "I want to evaluate NubeRush for my store",
    body: "Use the Request demo page to start a conversation with the NubeRush team.",
    cta: { label: "Request a demo", to: "/request-demo" },
  },
  {
    title: "I have a partnership or operational question",
    body: "Send the team a note describing what you'd like to discuss.",
    cta: { label: "Open the contact page", to: "/contact" },
  },
];

const MORE_LINKS: ReadonlyArray<{ label: string; to: string; body: string }> = [
  {
    label: "Contact",
    to: "/contact",
    body: "Ways to reach the team for inquiries beyond support.",
  },
  {
    label: "Request demo",
    to: "/request-demo",
    body: "What to include when you reach out to evaluate the platform.",
  },
  {
    label: "How it works",
    to: "/how-it-works",
    body: "An honest walkthrough of how stores get onto the platform.",
  },
  {
    label: "Features",
    to: "/features",
    body: "What the operator surface ships today.",
  },
];

const MOBILE_TOPIC_TITLES: Record<string, string> = {
  "I run a store on NubeRush and need help": "Store help",
  "I want to evaluate NubeRush for my store": "Evaluate NubeRush",
  "I have a partnership or operational question": "Partnerships",
};

export function SupportPage() {
  const isMobileCopy = useMobileCopy();

  return (
    <>
      <PublicPageHeader
        eyebrow="Support"
        title="Support and contact."
        mobileTitle="Support."
        description="A starting point for stores, operators, and partners. NubeRush does not run a public ticketing system; support flows through email and operator contact channels."
        mobileDescription="Start here for store, demo, or partner questions."
      />

      <PublicSection
        title="Common starting points"
        mobileTitle="Starting points."
        description="Find the closest match to your situation, then reach out to the team."
        mobileDescription="Pick the closest path."
      >
        <ul className="grid gap-4 md:grid-cols-3">
          {TOPICS.map((topic) => (
            <li
              key={topic.title}
              className="premium-glass-soft rounded-lg p-5"
            >
              <p className="text-sm font-semibold text-foreground">
                {isMobileCopy
                  ? MOBILE_TOPIC_TITLES[topic.title] ?? topic.title
                  : topic.title}
              </p>
              <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
                {topic.body}
              </p>
              <p className="mt-3 text-sm">
                {topic.cta.to ? (
                  <Link
                    to={topic.cta.to}
                    className="font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
                  >
                    {topic.cta.label} →
                  </Link>
                ) : topic.cta.mailto ? (
                  <a
                    href={topic.cta.mailto}
                    className="font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
                  >
                    {topic.cta.label} →
                  </a>
                ) : null}
              </p>
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        title="Email"
        mobileTitle="Email."
        description="The most reliable way to reach the team. Response time varies by request and is not guaranteed."
        mobileDescription="The main support channel today."
        tone="muted"
      >
        <div className="premium-glass-soft rounded-lg p-5">
          <p className="text-base">
            <a
              href="mailto:info@nuberush.com"
              className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              info@nuberush.com
            </a>
          </p>
          <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
            A formal help center and FAQ are planned for a later phase. Until
            then, email is the supported channel.
          </p>
        </div>
      </PublicSection>

      <PublicSection
        eyebrow="More resources"
        title="Other places to look."
        mobileTitle="More resources."
        description="If support isn't quite what you need, these pages cover the rest of the platform's public surface."
        mobileDescription="Other public pages that may help."
      >
        <ul className="grid gap-4 sm:grid-cols-2">
          {MORE_LINKS.map((link) => (
            <li key={link.to}>
              <Link
                to={link.to}
                className="premium-glass-soft block rounded-lg p-5 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <p className="text-sm font-semibold text-foreground">
                  {link.label}
                </p>
                <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
                  {link.body}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </PublicSection>
    </>
  );
}

export default SupportPage;
