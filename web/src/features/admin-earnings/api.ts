// Admin earnings API layer. One read-only function over the backend
// `GET /admin/earnings` endpoint. Routes through `apiRequest` so error
// normalisation and Bearer attach stay centralised.

import { apiRequest } from "@/api";

import type { AdminEarningsSummary } from "./types";

export function getAdminEarnings(
  signal?: AbortSignal,
): Promise<AdminEarningsSummary> {
  return apiRequest<AdminEarningsSummary>("/admin/earnings", {
    method: "GET",
    signal,
  });
}
