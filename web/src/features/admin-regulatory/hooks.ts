// F2.26.6.B: query-key factory + TanStack Query hooks for the admin
// Regulatory Intelligence feature (compliance alerts + decision trail).
//
// One flat module for this foundation phase: the key factory, the three
// read hooks, and the three lifecycle mutation hooks. No page UI, no nav,
// no route wiring — just the data layer.
//
// Hard rules baked in (mirroring features/audit, features/admin-compliance):
//   - No useAuth / currentUser inspection, no role-based gating. The backend
//     authorises every call via `require_admin`; 401/403/404 surface through
//     the centralized `apiRequest` error path.
//   - No Supabase / session / store-context imports.
//   - No optimistic updates, no manual setQueryData, no client-side sort.
//   - Reads forward the TanStack `signal` to the api layer for cancellation.
//   - Mutations relay only — all lifecycle behaviour is server-side.

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import {
  acknowledgeAdminRegulatoryAlert,
  dismissAdminRegulatoryAlert,
  getAdminRegulatoryAlert,
  getAdminRegulatoryAlertDecisions,
  getAdminRegulatoryAlerts,
  resolveAdminRegulatoryAlert,
} from "./api";
import type {
  ComplianceAlert,
  ComplianceAlertActionRequest,
  ComplianceAlertFilters,
  ComplianceAlertListResponse,
  ComplianceAlertResolveRequest,
  RegulatoryDecisionAuditLogListResponse,
  RegulatoryDecisionAuditLogParams,
} from "./types";

// --------------------------------------------------------------------- //
// Query-key factory
// --------------------------------------------------------------------- //
//
// Shape:
//   all              ── ["admin-regulatory"]
//   alerts(filters)  ── ["admin-regulatory", "alerts", filters]
//   alert(alertId)   ── ["admin-regulatory", "alert", alertId]
//   decisions(id, p) ── ["admin-regulatory", "alert", alertId, "decisions", p]
//
// The list surface ("alerts") and the per-alert surface ("alert") use
// distinct segments so they never collide on prefix invalidation. A
// concrete `decisions(id, params)` key extends `alert(id)`, so the decision
// trail lives in the alert's subtree — handy for bounded invalidation.

export const adminRegulatoryKeys = {
  /** Root namespace — prefix for nuking the whole feature cache. */
  all: ["admin-regulatory"] as const,

  /**
   * Concrete key for one alert-list filter snapshot. The filters object is
   * always present (defaults to `{}`) so the tuple shape stays stable;
   * different snapshots get distinct cache slots. The shared
   * `[...all, "alerts"]` prefix is what mutations invalidate to flush every
   * filtered list at once.
   */
  alerts: (filters: ComplianceAlertFilters = {}) =>
    [...adminRegulatoryKeys.all, "alerts", filters] as const,

  /** Concrete key for a single alert's detail. */
  alert: (alertId: string) =>
    [...adminRegulatoryKeys.all, "alert", alertId] as const,

  /**
   * Concrete key for one (alert, params) snapshot of the decision trail.
   * Extends `alert(alertId)`, so invalidating the alert subtree also flushes
   * its decisions; different param snapshots get distinct cache slots.
   */
  decisions: (
    alertId: string,
    params: RegulatoryDecisionAuditLogParams = {},
  ) =>
    [
      ...adminRegulatoryKeys.alert(alertId),
      "decisions",
      params,
    ] as const,
};

/** Prefix matching every alert-list snapshot, regardless of filters. */
function alertsListPrefix() {
  return [...adminRegulatoryKeys.all, "alerts"] as const;
}

/** Prefix matching every decision-trail snapshot for one alert. */
function decisionsPrefix(alertId: string) {
  return [...adminRegulatoryKeys.alert(alertId), "decisions"] as const;
}

// --------------------------------------------------------------------- //
// Read hooks
// --------------------------------------------------------------------- //

/** GET /admin/regulatory/alerts — paginated, filtered alert list. */
export function useAdminRegulatoryAlerts(
  filters: ComplianceAlertFilters = {},
): UseQueryResult<ComplianceAlertListResponse> {
  return useQuery({
    queryKey: adminRegulatoryKeys.alerts(filters),
    queryFn: ({ signal }) => getAdminRegulatoryAlerts(filters, signal),
  });
}

/**
 * GET /admin/regulatory/alerts/{alert_id} — single alert detail.
 *
 * Accepts `string | null | undefined` so a page can pass a possibly-absent
 * route param directly; the query stays idle until the id is non-empty
 * (same guard idiom as `useStoreAuditQuery`).
 */
export function useAdminRegulatoryAlert(
  alertId: string | null | undefined,
): UseQueryResult<ComplianceAlert> {
  const trimmedId = typeof alertId === "string" ? alertId.trim() : "";
  const enabled = trimmedId.length > 0;

  return useQuery({
    queryKey: adminRegulatoryKeys.alert(trimmedId),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useAdminRegulatoryAlert: alertId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getAdminRegulatoryAlert(trimmedId, signal);
    },
    enabled,
  });
}

/**
 * GET /admin/regulatory/alerts/{alert_id}/decisions — per-alert decision
 * trail. Idle until `alertId` is non-empty.
 */
export function useAdminRegulatoryAlertDecisions(
  alertId: string | null | undefined,
  params: RegulatoryDecisionAuditLogParams = {},
): UseQueryResult<RegulatoryDecisionAuditLogListResponse> {
  const trimmedId = typeof alertId === "string" ? alertId.trim() : "";
  const enabled = trimmedId.length > 0;

  return useQuery({
    queryKey: adminRegulatoryKeys.decisions(trimmedId, params),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useAdminRegulatoryAlertDecisions: alertId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getAdminRegulatoryAlertDecisions(trimmedId, params, signal);
    },
    enabled,
  });
}

// --------------------------------------------------------------------- //
// Mutation hooks
// --------------------------------------------------------------------- //
//
// On success every lifecycle mutation invalidates the same bounded subtree
// so the UI re-reads consistent state:
//   1. every alert-list snapshot      (alertsListPrefix)
//   2. the mutated alert's detail      (adminRegulatoryKeys.alert)
//   3. that alert's decision trail     (decisionsPrefix — a new audit row was
//      written server-side)
//
// `alert(alertId)` already prefixes the decision trail, so (2) implicitly
// covers (3); we invalidate the decision prefix explicitly as well to make
// the contract obvious and resilient to future key-shape changes.

/** Variables shared by the three lifecycle verbs that take a `reason`. */
export interface AdminRegulatoryAlertActionVariables {
  alertId: string;
  body: ComplianceAlertActionRequest;
}

/** Variables for the resolve verb (no_action / hold / ban). */
export interface AdminRegulatoryAlertResolveVariables {
  alertId: string;
  body: ComplianceAlertResolveRequest;
}

function invalidateAlertSubtree(
  queryClient: ReturnType<typeof useQueryClient>,
  alertId: string,
): void {
  queryClient.invalidateQueries({ queryKey: alertsListPrefix() });
  queryClient.invalidateQueries({
    queryKey: adminRegulatoryKeys.alert(alertId),
  });
  queryClient.invalidateQueries({ queryKey: decisionsPrefix(alertId) });
}

/** POST /admin/regulatory/alerts/{alert_id}/acknowledge */
export function useAcknowledgeAdminRegulatoryAlert(): UseMutationResult<
  ComplianceAlert,
  unknown,
  AdminRegulatoryAlertActionVariables
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, body }: AdminRegulatoryAlertActionVariables) =>
      acknowledgeAdminRegulatoryAlert(alertId, body),
    onSuccess: (_result, variables) => {
      invalidateAlertSubtree(queryClient, variables.alertId);
    },
  });
}

/** POST /admin/regulatory/alerts/{alert_id}/dismiss */
export function useDismissAdminRegulatoryAlert(): UseMutationResult<
  ComplianceAlert,
  unknown,
  AdminRegulatoryAlertActionVariables
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, body }: AdminRegulatoryAlertActionVariables) =>
      dismissAdminRegulatoryAlert(alertId, body),
    onSuccess: (_result, variables) => {
      invalidateAlertSubtree(queryClient, variables.alertId);
    },
  });
}

/** POST /admin/regulatory/alerts/{alert_id}/resolve */
export function useResolveAdminRegulatoryAlert(): UseMutationResult<
  ComplianceAlert,
  unknown,
  AdminRegulatoryAlertResolveVariables
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, body }: AdminRegulatoryAlertResolveVariables) =>
      resolveAdminRegulatoryAlert(alertId, body),
    onSuccess: (_result, variables) => {
      invalidateAlertSubtree(queryClient, variables.alertId);
    },
  });
}
