// Query-key factory for the admin-settings module.
//
//   adminSettingsKeys.all       ── ["admin-settings"]
//   adminSettingsKeys.snapshot() ── ["admin-settings", "snapshot"]
//
// Single endpoint today (`GET /admin/settings`). The `all` root stays
// available as the prefix-invalidation target for any future mutation
// that affects platform settings.
//
// Rules:
//   - Stable shape across renders.
//   - No store / role / route context in the key.
//   - No filters: the endpoint takes no query params.

export const adminSettingsKeys = {
  all: ["admin-settings"] as const,
  snapshot: () => [...adminSettingsKeys.all, "snapshot"] as const,
};
