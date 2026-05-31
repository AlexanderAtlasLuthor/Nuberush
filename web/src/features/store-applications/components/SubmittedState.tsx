// F2.24.C6 — Step 6 (Submitted / pending review). Terminal success state.
// Does NOT auto-login, create a session, or redirect into /app — applying
// is a reviewed application, not instant access.

import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

export function SubmittedState() {
  return (
    <div className="text-center" data-testid="apply-submitted">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
      </div>
      <h2 className="mt-5 text-2xl font-semibold tracking-tight text-foreground">
        Application submitted
      </h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
        Your store application is pending review. We'll contact you after the
        NubeRush team reviews your information. Access is only available once
        an administrator approves your store.
      </p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Link
          to="/"
          className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Back to home
        </Link>
        <Link
          to="/login"
          className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Go to sign in
        </Link>
      </div>
    </div>
  );
}

export default SubmittedState;
