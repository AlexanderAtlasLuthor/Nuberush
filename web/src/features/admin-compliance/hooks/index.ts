// F2.20.4: public barrel for the admin-compliance hooks namespace.
//
// Consumers should import from this barrel
// (`@/features/admin-compliance/hooks`) rather than reach into the
// individual files, so we can refactor internals without ripple
// changes.

export { adminComplianceQueryKeys } from "./queryKeys";
export { useAdminComplianceSummaryQuery } from "./useAdminComplianceSummaryQuery";
export { useAdminComplianceProductsQuery } from "./useAdminComplianceProductsQuery";
