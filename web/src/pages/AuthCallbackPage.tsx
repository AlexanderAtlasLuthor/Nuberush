import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { BrandMark } from '@/components/common/brand-mark';
import { supabase } from '@/lib/supabase';

// F2.25.4.C: Supabase auth-link landing page.
//
// The backend asks Supabase Auth to email approved owners a password
// setup / recovery link that redirects here ({APP_PUBLIC_BASE_URL}/auth/
// callback). Supabase owns the token; this page only detects that a
// session was established from the link and forwards the owner to
// /auth/set-password. It never reads, renders, or logs the token, the
// recovery code, or the raw URL contents, and it never calls the backend.
//
// Session detection is belt-and-suspenders so it works regardless of the
// Supabase flow type:
//   - detectSessionInUrl auto-consumes a hash (implicit) link and fires
//     onAuthStateChange (PASSWORD_RECOVERY / SIGNED_IN);
//   - a ?code= (PKCE) link is exchanged via exchangeCodeForSession;
//   - getSession() catches a session already established before mount.
// A short fallback timeout avoids spinning forever on an invalid/expired
// link.

const _FALLBACK_MS = 5000;

const AuthCallbackPage = () => {
  const navigate = useNavigate();
  const [hasError, setHasError] = useState(false);
  // Guard so we redirect / set error exactly once.
  const settled = useRef(false);

  useEffect(() => {
    const goSetPassword = () => {
      if (settled.current) return;
      settled.current = true;
      navigate('/auth/set-password', { replace: true });
    };

    const fail = () => {
      if (settled.current) return;
      settled.current = true;
      setHasError(true);
    };

    // 1. Surface an explicit auth error from the link without rendering the
    //    raw (possibly token-bearing) description.
    const hashParams = new URLSearchParams(
      window.location.hash.replace(/^#/, ''),
    );
    const queryParams = new URLSearchParams(window.location.search);
    const hasErrorParam =
      hashParams.has('error') ||
      hashParams.has('error_description') ||
      queryParams.has('error') ||
      queryParams.has('error_description');
    if (hasErrorParam) {
      fail();
      return;
    }

    // 2. Subscribe first so an async auto-consume (detectSessionInUrl) is
    //    not missed.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (
        (event === 'PASSWORD_RECOVERY' || event === 'SIGNED_IN') &&
        session
      ) {
        goSetPassword();
      }
    });

    // 3. PKCE links arrive as ?code=...; exchange it for a session.
    const code = queryParams.get('code');
    if (code) {
      supabase.auth
        .exchangeCodeForSession(code)
        .then(({ data, error }) => {
          if (error || !data.session) {
            fail();
            return;
          }
          goSetPassword();
        })
        .catch(() => fail());
    }

    // 4. A session may already exist (implicit link consumed before mount).
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (data.session) goSetPassword();
      })
      .catch(() => {
        /* handled by the fallback timeout */
      });

    // 5. Nothing established a session in time → safe error.
    const timeoutId = setTimeout(fail, _FALLBACK_MS);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeoutId);
    };
  }, [navigate]);

  return (
    <div className="public-ambient auth-ambient z-50 flex min-h-dvh flex-col overflow-x-hidden overflow-y-auto safe-top">
      <div className="flex flex-1 items-start justify-center px-5 pb-12 pt-32 md:items-center md:py-20">
        <div className="premium-ring w-full max-w-md rounded-[2rem] p-px">
          <div className="premium-glass rounded-[2rem] px-5 py-8 md:px-7">
            <div className="mb-7 text-center">
              <BrandMark className="mx-auto mb-4 h-16 w-16" />
              {hasError ? (
                <>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">
                    Link invalid or expired
                  </h1>
                  <p
                    role="alert"
                    aria-live="polite"
                    className="mt-3 rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-red-200"
                  >
                    This link is invalid or has expired.
                  </p>
                  <Link
                    to="/login"
                    className="mt-6 inline-block font-semibold text-primary transition-colors hover:text-primary/85"
                  >
                    Back to sign in
                  </Link>
                </>
              ) : (
                <>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">
                    Verifying your link…
                  </h1>
                  <p className="mt-2 inline-flex items-center gap-2 text-sm text-white/56">
                    <Loader2
                      className="h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    One moment while we confirm your activation link.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthCallbackPage;
