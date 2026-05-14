export const adminEarningsKeys = {
  all: ["admin-earnings"] as const,
  summary: () => [...adminEarningsKeys.all, "summary"] as const,
};
