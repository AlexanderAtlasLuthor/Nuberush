// F2.3 / F2.22.2.G: AuthProvider — single source of truth for the
// React-side session.
//
// What it owns:
//   - the current AuthUser (or null)
//   - the bootstrap-pass loading flag (the window between mount and the
//     first session check + /auth/me round-trip)
//   - login / logout / refreshSession actions
//
// What it does NOT own:
//   - role/permission decisions. Backend is the authority. The frontend
//     reads `user.role` only to decide UI visibility, never to
//     authorise data access. The router still hits the API and trusts
//     the API's 401/403.
//   - the access token. Since F2.22.2.G the token lives in the Supabase
//     session (persisted + auto-refreshed by the Supabase client). This
//     component never touches the token directly — it only reacts to
//     Supabase auth events and asks FastAPI who the user is.
//
// Bootstrap behaviour (F2.22.2.G):
//   - On mount, `supabase.auth.getSession()` reports whether a persisted
//     session exists. If it does, `GET /auth/me` resolves the app user;
//     if not, the app starts unauthenticated. Because the Supabase
//     session is persisted, a hard reload now keeps the user signed in.
//   - `supabase.auth.onAuthStateChange` keeps React state in sync with
//     later events: SIGNED_IN / TOKEN_REFRESHED re-fetch /auth/me,
//     SIGNED_OUT clears the user.

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { supabase } from "@/lib/supabase";
import * as authApi from "./auth.api";
import { AuthContext } from "./auth-context";
import type { AuthContextValue } from "./auth-context";
import type { AuthUser } from "./types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  // StrictMode in development double-invokes effects; the ref guards
  // against firing the bootstrap fetch twice on the same mount.
  const didBootstrap = useRef(false);

  // Bootstrap: read the persisted Supabase session, then resolve the app
  // user from FastAPI if a session exists.
  useEffect(() => {
    if (didBootstrap.current) return;
    didBootstrap.current = true;

    let active = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        if (!data.session) {
          // No persisted session → start unauthenticated.
          setIsLoading(false);
          return;
        }
        authApi
          .getMe()
          .then((u) => {
            if (active) setUser(u);
          })
          .catch(() => {
            // Session exists but /auth/me failed (token rejected, no
            // mapped public.users row, user gone). Treat as logged out.
            if (active) setUser(null);
          })
          .finally(() => {
            if (active) setIsLoading(false);
          });
      })
      .catch(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  // Keep React state in sync with Supabase auth events for the lifetime
  // of the provider.
  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT" || !session) {
        setUser(null);
        return;
      }
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
        // Defer out of the auth callback: calling Supabase APIs
        // (getMe → apiRequest → getSession) re-entrantly inside the
        // listener can deadlock the client's internal lock.
        setTimeout(() => {
          authApi
            .getMe()
            .then((u) => setUser(u))
            .catch(() => setUser(null));
        }, 0);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const login = useCallback<AuthContextValue["login"]>(
    async (credentials) => {
      setIsLoading(true);
      try {
        // authApi.login signs in via Supabase, then resolves the app
        // user from FastAPI /auth/me.
        const me = await authApi.login(credentials);
        setUser(me);
        return me;
      } catch (err) {
        // signInWithPassword or the follow-up /auth/me failed. End in a
        // clean logged-out state so the UI never shows stale auth.
        await authApi.logout().catch(() => {});
        setUser(null);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const logout = useCallback<AuthContextValue["logout"]>(() => {
    // Clear React state immediately; signOut also emits SIGNED_OUT,
    // which the listener handles idempotently.
    setUser(null);
    void authApi.logout().catch(() => {});
  }, []);

  const refreshSession = useCallback<AuthContextValue["refreshSession"]>(
    async () => {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setUser(null);
        return;
      }
      try {
        const me = await authApi.getMe();
        setUser(me);
      } catch (err) {
        setUser(null);
        throw err;
      }
    },
    [],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      refreshSession,
    }),
    [user, isLoading, login, logout, refreshSession],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}
