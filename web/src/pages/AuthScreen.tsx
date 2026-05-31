import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth';
import { getApiErrorMessage } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ArrowLeft, Phone, Loader2 } from 'lucide-react';
import { BrandMark } from '@/components/common/brand-mark';

// F2.3 / F2.22.2.G: real auth wiring.
//
// Behaviour:
//   - handleSubmit calls AuthProvider.login(), which signs in via
//     Supabase Auth (signInWithPassword) and then validates the session
//     by resolving the app user from FastAPI /auth/me.
//   - Success navigates to the route the user originally tried to reach
//     (or /app as the fallback).
//   - Errors are surfaced as user-readable text from getApiErrorMessage
//     (which handles ApiError, vanilla Error, strings, and unknowns) —
//     invalid Supabase credentials and a failed /auth/me both land here.
//   - Social/phone buttons are visually preserved but inert: no
//     OAuth/phone flow is wired.
//   - There is NO self-serve sign-up. Store owners apply via the public
//     /apply onboarding wizard (F2.24); the NubeRush team reviews the
//     application and the backend provisions the store + owner account.
//     The "apply" link at the bottom routes there. Admins still create
//     internal users via POST /auth/users.
//
// Visual-only changes should not alter the auth flow above.

const AuthScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading: authLoading } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // ProtectedRoute forwards the original location in router state.
  // Used by the redirect logic below only when the saved path is
  // compatible with the authenticated user's role; otherwise the user
  // is sent to /app so AppIndexRedirect can route by role.
  const fromState = location.state as { from?: { pathname?: string } } | null;
  const fromPath = fromState?.from?.pathname;

  const handleSubmit = async () => {
    if (!email || !password) {
      setErrorMsg('Email and password are required.');
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const me = await login({ email, password });
      // Honor `from` only when it's compatible with the user's role
      // area. Without this guard a stale `from` (e.g. /app/store
      // saved when an owner was kicked to /login) would override the
      // role-based redirect for a subsequent admin login, dropping
      // the admin into the store shell. Fallback `/app` defers to
      // AppIndexRedirect, which picks /app/admin vs /app/store by
      // role.
      const isAdminCompat = fromPath?.startsWith('/app/admin') ?? false;
      const isStoreCompat = fromPath?.startsWith('/app/store') ?? false;
      const isStoreUserRole =
        me.role === 'owner' ||
        me.role === 'manager' ||
        me.role === 'staff';
      const target =
        me.role === 'admin' && isAdminCompat
          ? fromPath!
          : isStoreUserRole && isStoreCompat
            ? fromPath!
            : '/app';
      navigate(target, { replace: true });
    } catch (err) {
      setErrorMsg(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSocial = () => {
    setErrorMsg('Social and phone sign-in are not yet supported.');
  };

  const isBusy = submitting || authLoading;

  return (
    <div className="public-ambient auth-ambient z-50 flex min-h-dvh flex-col overflow-x-hidden overflow-y-auto safe-top">
      {/* Back button — navigates to `/` (the public landing page).
          We don't use `navigate(-1)` because /login is often the
          first entry on the history stack (deep link, fresh tab,
          logout-then-login) and the back step would silently do
          nothing. */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-5 top-6 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/10 text-white shadow-lg backdrop-blur-xl transition-colors hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:top-8"
        aria-label="Back to landing page"
      >
        <ArrowLeft className="h-5 w-5" />
      </button>

      <div className="flex flex-1 items-start justify-center px-5 pb-12 pt-32 md:items-center md:py-20">
        <div className="premium-ring w-full max-w-md rounded-[2rem] p-px">
          <div className="premium-glass rounded-[2rem] px-5 py-8 md:px-7">
            {/* Logo */}
            <div className="mb-7 text-center">
              <BrandMark className="mx-auto mb-4 h-16 w-16" />
              <h1 className="text-3xl font-semibold tracking-tight text-white">
                Welcome Back
              </h1>
              <p className="mt-2 text-sm text-white/56">
                Sign in to continue
              </p>
            </div>

            {/* Social buttons — kept for visual continuity but inert: backend
                exposes no OAuth/phone flow yet. */}
            <div className="mb-5 grid gap-3">
              <button
                type="button"
                onClick={handleSocial}
                disabled
                aria-disabled="true"
                className="flex h-12 w-full cursor-not-allowed items-center justify-center gap-3 rounded-lg border border-white/10 bg-white/[0.06] py-3 text-sm font-medium text-white opacity-60"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Continue with Google
              </button>
              <button
                type="button"
                onClick={handleSocial}
                disabled
                aria-disabled="true"
                className="flex h-12 w-full cursor-not-allowed items-center justify-center gap-3 rounded-lg border border-white/10 bg-white/[0.06] py-3 text-sm font-medium text-white opacity-60"
              >
                <Phone className="h-5 w-5 text-primary" />
                Continue with Phone Number
              </button>
            </div>

            {/* Divider */}
            <div className="mb-5 flex items-center gap-4">
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-xs text-white/38">or</span>
              <div className="h-px flex-1 bg-white/10" />
            </div>

            {/* Email/Password */}
            <div className="mb-4 space-y-3">
              <Input
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isBusy}
                autoComplete="email"
                className="h-12 rounded-lg border-white/10 bg-white/[0.07] py-3 text-white placeholder:text-white/36 focus:ring-1 disabled:opacity-80"
              />
              <Input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isBusy}
                autoComplete="current-password"
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
              disabled={isBusy}
              className="premium-action h-12 w-full rounded-lg py-3 text-base font-semibold text-white disabled:opacity-85"
            >
              {submitting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Signing in…
                </span>
              ) : 'Sign In'}
            </Button>

            {/* Onboarding: store owners don't self-register — they apply,
                get reviewed, and the team provisions the account. Route
                the "sign up" affordance to the public /apply wizard. */}
            <p className="mt-6 text-center text-sm text-white/56">
              Want to sell on NubeRush?{' '}
              <Link
                to="/apply"
                className="font-semibold text-primary transition-colors hover:text-primary/85"
              >
                Apply to open a store
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthScreen;
