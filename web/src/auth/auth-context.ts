// F2.24.X5: AuthContext lives in its own module so AuthProvider.tsx can
// export only the component (Fast Refresh requires component-only files).
// The provider and the useAuth hook both import the context from here.

import { createContext } from "react";

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
