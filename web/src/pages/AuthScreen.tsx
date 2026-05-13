import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth';
import { getApiErrorMessage } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ArrowLeft, Phone, Flame, Loader2 } from 'lucide-react';

// F2.3: real auth wiring.
//
// What changed vs the F2.0/F2.1 placeholder:
//   - handleSubmit now calls AuthProvider.login() which POSTs to
//     FastAPI /auth/login and validates the issued token via /auth/me.
//   - The fake `setOnboardingStep` advancement is gone; success
//     navigates to the route the user originally tried to reach (or
//     /app as the fallback).
//   - Errors are surfaced as user-readable text from getApiErrorMessage
//     (which handles ApiError, vanilla Error, strings, and unknowns).
//   - Social/phone buttons are visually preserved but inert: the
//     backend exposes no OAuth/phone flow, and pretending otherwise
//     would re-introduce the prototype's fake auth.
//   - Sign-up mode shows the same message the backend returns from
//     POST /auth/register (deprecated) — public registration is
//     disabled by design; admins create users via POST /auth/users.
//
// Visual layout is preserved on purpose. F2.3 is wiring, not redesign.

const AuthScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading: authLoading } = useAuth();

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
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
    if (mode === 'signup') {
      setErrorMsg(
        'Public registration is disabled. Please contact your administrator.',
      );
      return;
    }
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
    <div className="fixed inset-0 flex flex-col z-50 safe-top" style={{ backgroundColor: '#0A0A0F' }}>
      {/* Back button — navigates to `/` (the public landing page).
          We don't use `navigate(-1)` because /login is often the
          first entry on the history stack (deep link, fresh tab,
          logout-then-login) and the back step would silently do
          nothing. */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute top-12 left-5 w-10 h-10 rounded-full flex items-center justify-center"
        style={{ backgroundColor: '#13131A' }}
        aria-label="Back to landing page"
      >
        <ArrowLeft className="w-5 h-5 text-white" />
      </button>

      <div className="flex-1 flex flex-col px-6 pt-24">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ backgroundColor: '#FF6B2C' }}>
            <Flame className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">
            {mode === 'signin' ? 'Welcome Back' : 'Create Account'}
          </h1>
          <p className="text-sm mt-1" style={{ color: '#888' }}>
            {mode === 'signin' ? 'Sign in to continue' : 'Join NubeRush today'}
          </p>
        </div>

        {/* Social buttons — kept for visual continuity but inert: backend
            exposes no OAuth/phone flow yet. */}
        <div className="space-y-3 mb-6">
          <button
            type="button"
            onClick={handleSocial}
            disabled
            aria-disabled="true"
            className="w-full h-13 py-3.5 rounded-xl flex items-center justify-center gap-3 font-medium text-white opacity-60 cursor-not-allowed"
            style={{ backgroundColor: '#13131A', border: '1px solid #1E1E2A' }}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Continue with Google
          </button>
          <button
            type="button"
            onClick={handleSocial}
            disabled
            aria-disabled="true"
            className="w-full h-13 py-3.5 rounded-xl flex items-center justify-center gap-3 font-medium text-white opacity-60 cursor-not-allowed"
            style={{ backgroundColor: '#13131A', border: '1px solid #1E1E2A' }}
          >
            <Phone className="w-5 h-5" style={{ color: '#FF6B2C' }} />
            Continue with Phone Number
          </button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1 h-px" style={{ backgroundColor: '#1E1E2A' }} />
          <span className="text-xs" style={{ color: '#555' }}>or</span>
          <div className="flex-1 h-px" style={{ backgroundColor: '#1E1E2A' }} />
        </div>

        {/* Email/Password */}
        <div className="space-y-3 mb-4">
          <Input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isBusy}
            autoComplete="email"
            className="h-13 py-3.5 rounded-xl text-white border-none placeholder:text-gray-500 focus:ring-1"
            style={{ backgroundColor: '#13131A' }}
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isBusy}
            autoComplete="current-password"
            className="h-13 py-3.5 rounded-xl text-white border-none placeholder:text-gray-500 focus:ring-1"
            style={{ backgroundColor: '#13131A' }}
          />
        </div>

        {errorMsg && (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm mb-3 px-1"
            style={{ color: '#FF6B6B' }}
          >
            {errorMsg}
          </p>
        )}

        <Button
          type="button"
          onClick={handleSubmit}
          disabled={isBusy}
          className="w-full h-13 py-3.5 rounded-xl text-white font-semibold text-base"
          style={{ backgroundColor: '#FF6B2C' }}
        >
          {submitting ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Signing in…
            </span>
          ) : mode === 'signin' ? 'Sign In' : 'Sign Up'}
        </Button>

        {/* Toggle mode */}
        <p className="text-center mt-6 text-sm" style={{ color: '#888' }}>
          {mode === 'signin' ? "Don't have an account? " : 'Already have an account? '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'signin' ? 'signup' : 'signin');
              setErrorMsg(null);
            }}
            className="font-semibold"
            style={{ color: '#FF6B2C' }}
          >
            {mode === 'signin' ? 'Sign Up' : 'Sign In'}
          </button>
        </p>
      </div>
    </div>
  );
};

export default AuthScreen;
