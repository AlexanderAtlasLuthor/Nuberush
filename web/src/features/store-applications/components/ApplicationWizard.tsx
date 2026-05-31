// F2.24.C6 — public merchant onboarding wizard orchestrator.
//
// Owns the multi-step state, per-step UX validation, the network submit
// (via ./api), and the terminal pending-review state. The backend is the
// authority; this only guards UX so a known-bad value doesn't round-trip
// for a 422, and translates backend errors into friendly copy.
//
// No Supabase, no session, no redirect into /app — applying is a reviewed
// application, not instant access.

import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { isApiError } from "@/api";

import { submitStoreApplication } from "../api";
import {
  INITIAL_VALUES,
  toSubmitPayload,
  validateStep,
  type ApplicationFormErrors,
  type ApplicationFormValues,
  type StringFieldKey,
} from "./form";
import { BusinessInfoStep } from "./BusinessInfoStep";
import { OwnerInfoStep } from "./OwnerInfoStep";
import { OperationsStep } from "./OperationsStep";
import { ReviewStep } from "./ReviewStep";
import { SubmittedState } from "./SubmittedState";

// Friendly, non-leaking copy for the backend error branches.
const DUPLICATE_MESSAGE =
  "An application for this owner email is already active or under review.";
const VALIDATION_MESSAGE =
  "Some of the information needs attention. Please review your entries and try again.";
const GENERIC_MESSAGE =
  "We couldn't submit your application. Please review your information and try again.";

// Content steps (1..4). Index 0 is the welcome screen.
const CONTENT_STEPS = [
  { step: 1, label: "Business" },
  { step: 2, label: "Owner" },
  { step: 3, label: "Operations" },
  { step: 4, label: "Review" },
] as const;

const LAST_STEP = 4;

export function ApplicationWizard() {
  const [stepIndex, setStepIndex] = useState(0); // 0 = welcome
  const [values, setValues] = useState<ApplicationFormValues>(INITIAL_VALUES);
  const [errors, setErrors] = useState<ApplicationFormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (key: StringFieldKey, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleTermsChange = (accepted: boolean) => {
    setValues((prev) => ({ ...prev, terms_accepted: accepted }));
    setErrors((prev) => {
      if (!prev.terms_accepted) return prev;
      const next = { ...prev };
      delete next.terms_accepted;
      return next;
    });
  };

  const goToStart = () => {
    setStepIndex(1);
    setSubmitError(null);
  };

  const handleNext = () => {
    const stepErrors = validateStep(stepIndex, values);
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      return;
    }
    setErrors({});
    setStepIndex((s) => Math.min(s + 1, LAST_STEP));
  };

  const handleBack = () => {
    setSubmitError(null);
    setErrors({});
    setStepIndex((s) => Math.max(s - 1, 1));
  };

  const handleSubmit = async () => {
    const stepErrors = validateStep(LAST_STEP, values);
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      return;
    }
    if (isSubmitting) return;

    setErrors({});
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      await submitStoreApplication(toSubmitPayload(values));
      setSubmitted(true);
    } catch (err) {
      if (isApiError(err) && err.status === 409) {
        setSubmitError(DUPLICATE_MESSAGE);
      } else if (isApiError(err) && err.status === 422) {
        setSubmitError(VALIDATION_MESSAGE);
      } else {
        setSubmitError(GENERIC_MESSAGE);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return <SubmittedState />;
  }

  // -------- Welcome --------
  if (stepIndex === 0) {
    return (
      <div className="text-center" data-testid="apply-welcome">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
          Apply to join NubeRush
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          NubeRush helps stores manage their operations. This is a reviewed
          application — completing the form does not guarantee approval. A
          NubeRush administrator will review the information you submit, and
          you'll be contacted after that review. Access is only available
          once your store is approved.
        </p>
        <ul className="mx-auto mt-5 inline-block space-y-2 text-left text-sm text-foreground/90">
          <li>• Every store is reviewed before activation.</li>
          <li>• Approval is not guaranteed.</li>
          <li>• We'll reach out using the owner contact details you provide.</li>
        </ul>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button type="button" onClick={goToStart} data-testid="apply-start">
            Start application
          </Button>
          <Link
            to="/for-stores"
            className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Learn more
          </Link>
        </div>
      </div>
    );
  }

  // -------- Steps 1..4 --------
  const isLast = stepIndex === LAST_STEP;

  return (
    <div data-testid="apply-wizard">
      {/* Progress indicator */}
      <ol
        className="mb-6 flex items-center gap-2"
        aria-label="Application progress"
        data-testid="apply-progress"
      >
        {CONTENT_STEPS.map(({ step, label }) => {
          const state =
            step === stepIndex
              ? "current"
              : step < stepIndex
                ? "complete"
                : "upcoming";
          return (
            <li key={step} className="flex flex-1 flex-col gap-1.5">
              <span
                aria-current={state === "current" ? "step" : undefined}
                className={
                  "h-1.5 w-full rounded-full " +
                  (state === "upcoming" ? "bg-border" : "bg-primary")
                }
              />
              <span
                className={
                  "text-xs " +
                  (state === "current"
                    ? "font-semibold text-foreground"
                    : "text-muted-foreground")
                }
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="sr-only" aria-live="polite">
        Step {stepIndex} of {LAST_STEP}
      </p>

      {stepIndex === 1 && (
        <BusinessInfoStep
          values={values}
          errors={errors}
          onChange={handleChange}
          disabled={isSubmitting}
        />
      )}
      {stepIndex === 2 && (
        <OwnerInfoStep
          values={values}
          errors={errors}
          onChange={handleChange}
          disabled={isSubmitting}
        />
      )}
      {stepIndex === 3 && (
        <OperationsStep
          values={values}
          errors={errors}
          onChange={handleChange}
          disabled={isSubmitting}
        />
      )}
      {stepIndex === 4 && (
        <ReviewStep
          values={values}
          errors={errors}
          onTermsChange={handleTermsChange}
          disabled={isSubmitting}
        />
      )}

      {submitError ? (
        <p
          role="alert"
          aria-live="polite"
          className="mt-6 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          data-testid="apply-submit-error"
        >
          {submitError}
        </p>
      ) : null}

      <div className="mt-8 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={handleBack}
          disabled={isSubmitting}
          data-testid="apply-back"
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden="true" />
          Back
        </Button>
        {isLast ? (
          <Button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isSubmitting}
            data-testid="apply-submit"
          >
            {isSubmitting ? "Submitting…" : "Submit application"}
          </Button>
        ) : (
          <Button
            type="button"
            onClick={handleNext}
            disabled={isSubmitting}
            data-testid="apply-next"
          >
            Continue
            <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
          </Button>
        )}
      </div>
    </div>
  );
}

export default ApplicationWizard;
