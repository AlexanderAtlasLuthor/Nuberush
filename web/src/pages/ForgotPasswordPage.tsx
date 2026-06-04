import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { getApiErrorMessage } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { BrandMark } from '@/components/common/brand-mark';
import { supabase } from '@/lib/supabase';

// F2.25.5: user-initiated "Forgot password" request page.
//
// Reuses the F2.25.4 consume/set-password half: Supabase Auth emails a
// recovery link to {origin}/auth/callback, which forwards to
// /auth/set-password where the owner calls supabase.auth.updateUser. This
// page only triggers the email — Supabase owns the token and never returns
// it here, and FastAPI is not involved (no custom reset token, no backend
// endpoint).
//
// Anti-enumeration: the same generic confirmation is shown whether or not
// an account exists, and Supabase errors never reveal account state. No
// token is ever rendered or logged.

// Conservative client-side shape check (final validation is Supabase's).
const _EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const _GENERIC_SUCCESS =
  'If an account exists for that email, a reset link has been sent.';

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async () => {
    const trimmed = email.trim();
    if (!trimmed) {
      setErrorMsg('Email is required.');
      return;
    }
    if (!_EMAIL_RE.test(trimmed)) {
      setErrorMsg('Enter a valid email address.');
      return;
    }

    setErrorMsg(null);
    setSubmitting(true);
    try {
      const redirectTo = `${window.location.origin}/auth/callback`;
      await supabase.auth.resetPasswordForEmail(trimmed, { redirectTo });
      // Always show the same generic confirmation — never reveal whether
      // the account exists.
      setDone(true);
    } catch {
      // Safe, generic failure — no raw Supabase detail, no account state.
      setErrorMsg(
        'We could not process that request right now. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="public-ambient auth-ambient z-50 flex min-h-dvh flex-col overflow-x-hidden overflow-y-auto safe-top">
      <div className="flex flex-1 items-start justify-center px-5 pb-12 pt-32 md:items-center md:py-20">
        <div className="premium-ring w-full max-w-md rounded-[2rem] p-px">
          <div className="premium-glass rounded-[2rem] px-5 py-8 md:px-7">
            <div className="mb-7 text-center">
              <BrandMark className="mx-auto mb-4 h-16 w-16" />
              <h1 className="text-3xl font-semibold tracking-tight text-white">
                Reset your password
              </h1>
              <p className="mt-2 text-sm text-white/56">
                Enter your email and we'll send you a reset link.
              </p>
            </div>

            {done ? (
              <p
                role="status"
                aria-live="polite"
                className="mb-3 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-3 text-sm text-white/80"
              >
                {_GENERIC_SUCCESS}
              </p>
            ) : (
              <>
                <div className="mb-4">
                  <Input
                    type="email"
                    placeholder="Email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={submitting}
                    autoComplete="email"
                    className="h-12 rounded-lg border-white/10 bg-white/[0.07] py-3 text-white placeholder:text-white/36 focus:ring-1 disabled:opacity-80"
                  />
                </div>

                {errorMsg && (
                  <p
                    role="alert"
                    aria-live="polite"
                    className="mb-3 rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-red-200"
                  >
                    {errorMsg}
                  </p>
                )}

                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="premium-action h-12 w-full rounded-lg py-3 text-base font-semibold text-white disabled:opacity-85"
                >
                  {submitting ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2
                        className="w-4 h-4 animate-spin"
                        aria-hidden="true"
                      />
                      Sending…
                    </span>
                  ) : (
                    'Send reset link'
                  )}
                </Button>
              </>
            )}

            <p className="mt-6 text-center text-sm text-white/56">
              <Link
                to="/login"
                className="font-semibold text-primary transition-colors hover:text-primary/85"
              >
                Back to sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
