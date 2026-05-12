// F2.3: AuthProvider — single source of truth for the React-side session.
//
// What it owns:
//   - the current AuthUser (or null)
//   - the bootstrap-pass loading flag (for the brief window between
//     mount and the first /auth/me round-trip when a token exists)
//   - login / logout / refreshSession actions
//
// What it does NOT own:
//   - role/permission decisions. Backend is the authority. The frontend
//     reads `user.role` only to decide UI visibility (later subphases),
//     never to authorise data access. The router still hits the API and
//     trusts the API's 401/403.
//   - token storage policy. The api/session-token holder is the only
//     place a token actually lives. This component just orchestrates
//     when to set/clear it.
//
// Bootstrap behaviour:
//   - On mount, if a token already exists in the api/session-token
//     holder, validate it via /auth/me before rendering authenticated
//     children. With F2.2's in-memory holder this almost always
//     short-circuits to "no token → not authenticated" on first paint
//     because a hard reload empties the holder.
//   - TODO(F2.5+): once the backend exposes a session cookie or refresh
//     endpoint, drop the `if (!token)` shortcut so /auth/me always runs
//     at boot — the cookie will let the server identify the user even
//     when the in-memory access_token is gone.

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/api";
import * as authApi from "./auth.api";
import type { AuthUser, LoginCredentials } from "./types";

export interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<AuthUser>;
  logout: () => void;
  refreshSession: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  // StrictMode in development double-invokes effects; the ref guards
  // against firing the bootstrap fetch twice on the same mount.
  const didBootstrap = useRef(false);

  useEffect(() => {
    if (didBootstrap.current) return;
    didBootstrap.current = true;

    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    authApi
      .getMe(controller.signal)
      .then((u) => {
        setUser(u);
      })
      .catch(() => {
        // Token rejected by /auth/me (expired, revoked, user gone). Drop
        // it so the user lands on /login cleanly instead of a half-auth
        // state.
        clearAccessToken();
        setUser(null);
      })
      .finally(() => {
        setIsLoading(false);
      });

    return () => controller.abort();
  }, []);

  const login = useCallback<AuthContextValue["login"]>(
    async (credentials) => {
      setIsLoading(true);
      try {
        const { access_token } = await authApi.login(credentials);
        setAccessToken(access_token);
        const me = await authApi.getMe();
        setUser(me);
        return me;
      } catch (err) {
        // Either /auth/login or the follow-up /auth/me failed. In both
        // cases we end in a clean "logged out" state so the UI does not
        // show stale auth.
        clearAccessToken();
        setUser(null);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const logout = useCallback<AuthContextValue["logout"]>(() => {
    clearAccessToken();
    setUser(null);
  }, []);

  const refreshSession = useCallback<AuthContextValue["refreshSession"]>(
    async () => {
      if (!getAccessToken()) {
        setUser(null);
        return;
      }
      try {
        const me = await authApi.getMe();
        setUser(me);
      } catch (err) {
        clearAccessToken();
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
