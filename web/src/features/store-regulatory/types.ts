// Store-scoped Regulatory wire types (F2.27.6).
//
// 1:1 mirror of the store-safe backend schemas in
// `backend/app/schemas/regulatory.py`:
//   - StoreComplianceAlertRead
//   - StoreComplianceAlertListResponse
//
// These deliberately OMIT every admin decision/resolution field
// (`match_id`, `resolution_note`, `resolved_by_user_id`, `resolved_at`) and the
// decision trail. The Store Panel only reads advisory alerts for products it
// carries. Wire fields stay snake_case to match the backend exactly.

/** Backend: `ComplianceAlertStatus`. */
export type StoreRegulatoryAlertStatus =
  | "open"
  | "acknowledged"
  | "actioned"
  | "dismissed";

/** Backend: `ComplianceAlertSeverity`. */
export type StoreRegulatoryAlertSeverity =
  | "low"
  | "medium"
  | "high"
  | "critical";

/** Backend: `ComplianceRecommendedAction` (advisory only, never applied). */
export type StoreRegulatoryRecommendedAction = "none" | "hold" | "ban";

/** Backend: `RegulatoryNoticeType`. */
export type StoreRegulatoryNoticeType =
  | "authorized_product_list"
  | "enforcement_notice"
  | "advisory"
  | "retailer_guidance"
  | "manual_snapshot";

export interface StoreRegulatoryAlert {
  id: string;
  notice_id: string;
  product_id: string;
  severity: StoreRegulatoryAlertSeverity;
  status: StoreRegulatoryAlertStatus;
  recommended_action: StoreRegulatoryRecommendedAction;
  created_at: string;
  updated_at: string;
  notice_title: string | null;
  notice_type: StoreRegulatoryNoticeType | null;
  notice_published_at: string | null;
  product_name: string | null;
}

export interface StoreRegulatoryAlertsResponse {
  items: StoreRegulatoryAlert[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Detail endpoint returns a single store-safe alert (same shape as a list
 * item); aliased for call-site clarity.
 */
export type StoreRegulatoryAlertDetailResponse = StoreRegulatoryAlert;

export interface StoreRegulatoryFilters {
  status?: StoreRegulatoryAlertStatus;
  severity?: StoreRegulatoryAlertSeverity;
  recommended_action?: StoreRegulatoryRecommendedAction;
  product_id?: string;
  limit?: number;
  offset?: number;
}
