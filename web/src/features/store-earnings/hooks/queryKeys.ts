export const storeEarningsKeys = {
  all: ["store-earnings"] as const,
  summary: (storeId: string) =>
    [...storeEarningsKeys.all, "summary", storeId] as const,
};
