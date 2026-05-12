// F2.4: hook to read the StoreContext.
//
// Throws on a missing provider for the same reason useAuth does: a
// missing provider is a programmer error that would otherwise surface
// as a confusing null-deref deep in a feature page. Failing loud here
// keeps the stack pointed at the misuse.

import { useContext } from "react";
import { StoreContext } from "./StoreProvider";
import type { StoreContextState } from "./store-context.types";

export function useStoreContext(): StoreContextState {
  const ctx = useContext(StoreContext);
  if (ctx === null) {
    throw new Error(
      "useStoreContext must be used within a <StoreProvider>",
    );
  }
  return ctx;
}
