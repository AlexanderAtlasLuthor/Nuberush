// F2.24.X5: StoreContext lives in its own module so StoreProvider.tsx can
// export only the component (Fast Refresh requires component-only files).
// The provider and the useStoreContext hook both import the context here.
// (The StoreContextState shape already lives in ./store-context.types.)

import { createContext } from "react";

import type { StoreContextState } from "./store-context.types";

export const StoreContext = createContext<StoreContextState | null>(null);
