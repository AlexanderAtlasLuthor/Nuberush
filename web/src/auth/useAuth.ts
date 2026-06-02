// F2.3: hook to read the AuthContext.
//
// The throw is deliberate: a missing provider is a programmer error
// that would otherwise show up as a confusing "cannot read property
// 'user' of null" much later in the render tree. Failing loud here
// keeps the stack trace pointed at the misuse.

import { useContext } from "react";
import { AuthContext } from "./auth-context";
import type { AuthContextValue } from "./auth-context";

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
