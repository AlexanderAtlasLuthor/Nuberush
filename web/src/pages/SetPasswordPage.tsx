import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { getApiErrorMessage } from '@/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { BrandMark } from '@/components/common/brand-mark';
import { supabase } from '@/lib/supabase';

// F2.25.4.D: owner password-setup page.
//
// Reached from /auth/callback once a Supabase recovery/activation session
// is established. The owner chooses their own password via
// supabase.auth.updateUser — FastAPI never sees a plaintext password and
// never issues a token. On success the USER_UPDATED event lets AuthProvider
// resolve the app user, so /app lands authenticated.
//
// Guard: with no Supabase session the page is unreachable legitimately, so
// it redirects to /login. No token or password is ever rendered or logged.

const _MIN_PASSWORD_LENGTH = 8;

const SetPasswordPage = () => {
  const navigate = useNavigate();

  const [checkingSession, setCheckingSession] = useState(true);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Require a session (the recovery/activation link must have established
  // one); otherwise this page is not legitimately reachable.
  useEffect(() => {
    let active = true;
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        if (!data.session) {
          navigate('/login', { replace: true });
          return;
        }
        setCheckingSession(false);
      })
      .catch(() => {
        if (active) navigate('/login', { replace: true });
      });
    return () => {
      active = false;
    };
  }, [navigate]);

  const handleSubmit = async () => {
    if (!password || !confirm) {
      setErrorMsg('Both password fields are required.');
      return;
    }
    if (password.length < _MIN_PASSWORD_LENGTH) {
      setErrorMsg(
        `Password must be at least ${_MIN_PASSWORD_LENGTH} characters.`,
      );
      return;
    }
    if (password !== confirm) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    setErrorMsg(null);
    setSubmitting(true);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) {
        setErrorMsg(getApiErrorMessage(error));
        return;
      }
      navigate('/app', { replace: true });
    } catch (err) {
      setErrorMsg(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (checkingSession) {
    return (
      <div className="public-ambient auth-ambient z-50 flex min-h-dvh flex-col overflow-x-hidden overflow-y-auto safe-top">
        <div className="flex flex-1 items-center justify-center px-5">
          <p className="inline-flex items-center gap-2 text-sm text-white/56">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="public-ambient auth-ambient z-50 flex min-h-dvh flex-col overflow-x-hidden overflow-y-auto safe-top">
      <div className="flex flex-1 items-start justify-center px-5 pb-12 pt-32 md:items-center md:py-20">
        <div className="premium-ring w-full max-w-md rounded-[2rem] p-px">
          <div className="premium-glass rounded-[2rem] px-5 py-8 md:px-7">
            <div className="mb-7 text-center">
              <BrandMark className="mx-auto mb-4 h-16 w-16" />
              <h1 className="text-3xl font-semibold tracking-tight text-white">
                Set your password
              </h1>
              <p className="mt-2 text-sm text-white/56">
                Choose a password to finish activating your account.
              </p>
            </div>

            <div className="mb-4 space-y-3">
              <Input
                type="password"
                placeholder="New password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                autoComplete="new-password"
                className="h-12 rounded-lg border-white/10 bg-white/[0.07] py-3 text-white placeholder:text-white/36 focus:ring-1 disabled:opacity-80"
              />
              <Input
                type="password"
                placeholder="Confirm password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={submitting}
                autoComplete="new-password"
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
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Saving…
                </span>
              ) : (
                'Set password'
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SetPasswordPage;
