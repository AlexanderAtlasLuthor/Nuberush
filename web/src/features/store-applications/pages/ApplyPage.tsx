// F2.24.C6 — public /apply page. Merchant onboarding wizard wrapped in the
// public design system. Public, unauthenticated; renders the single page
// h1 via PublicPageHeader (step titles are h2) so the public-route
// single-h1 contract holds.

import { PublicPageHeader } from "@/features/public/components/PublicPageHeader";
import { ApplicationWizard } from "../components/ApplicationWizard";

export function ApplyPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow="Partner with NubeRush"
        title="Apply to bring your store onto NubeRush"
        mobileTitle="Apply your store"
        description="Submit your store details for review. NubeRush reviews every store before activation — applying does not guarantee approval, and you'll be contacted after our team reviews your information."
        mobileDescription="Submit your store for review. Every store is reviewed before activation."
      />
      <section className="w-full py-12 md:py-16">
        <div className="container">
          <div className="premium-ring mx-auto max-w-3xl rounded-[2rem] p-px">
            <div className="premium-glass rounded-[2rem] px-5 py-8 md:px-10 md:py-12">
              <ApplicationWizard />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

export default ApplyPage;
