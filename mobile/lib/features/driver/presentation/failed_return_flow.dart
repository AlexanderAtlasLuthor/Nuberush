// NubeRush Driver — Failed Delivery / Return flow gating (Dr.1.5.H).
//
// DISPLAY-ONLY helpers deciding which failed-delivery / return surfaces are
// relevant, derived strictly from the backend-reported assignment status,
// delivery `state`, and the existing compliance-availability map. They compute
// NO authority: the backend remains the single authority for the fail and
// return-to-store lifecycle, and for the final STORE-SIDE return confirmation
// (`confirm-driver-return`), which mobile never calls. Unknown / unrelated
// states resolve to `notRelevant`. No order cancel, no inventory release, and
// no fabricated states live here — every signal comes from a real read model.

import '../domain/driver_assignment.dart';
import '../domain/driver_delivery_state.dart';
import 'driver_compliance_action.dart';

/// The single failed/return stage the driver is currently in, derived only from
/// backend-loaded data. Stages are mutually exclusive for known states.
enum FailedReturnStage {
  /// A failed delivery may be reported now (existing `fail` action available).
  reportFail,

  /// The order must be returned to the store (existing `return-to-store` action
  /// is available — it starts the return while `delivery_failed` and marks
  /// arrival while `returning_to_store`).
  returnToStore,

  /// The driver has returned the order; only the store-side confirmation
  /// remains. Driver mobile has nothing left to submit.
  returnPending,

  /// Nothing failed/return related applies at the current backend state.
  notRelevant,
}

/// True when reporting a failed delivery is offered by the existing map.
bool failReportRelevant(List<DriverComplianceAction> compliance) =>
    compliance.contains(DriverComplianceAction.reportFailedDelivery);

/// True when the existing return-to-store action is offered.
bool returnToStoreRelevant(List<DriverComplianceAction> compliance) =>
    compliance.contains(DriverComplianceAction.returnToStore);

/// True when the order has been returned to the store and only the store-side
/// confirmation remains. Derived strictly from backend-loaded state — never
/// fabricated. `returned_to_store` is the backend delivery state; the order
/// summary may also report a `returned` status / `returned_at` timestamp.
bool returnPending({
  DriverAssignmentDetail? detail,
  DriverDeliveryState? deliveryState,
}) {
  if (deliveryState?.state == 'returned_to_store') return true;
  final order = detail?.order;
  if (order != null &&
      (order.status == 'returned' || order.returnedAt != null)) {
    return true;
  }
  return false;
}

/// Resolve the current stage. Report-fail and return-to-store come from the
/// existing availability map; return-pending from backend-loaded state.
FailedReturnStage failedReturnStage({
  required List<DriverComplianceAction> compliance,
  DriverAssignmentDetail? detail,
  DriverDeliveryState? deliveryState,
}) {
  if (failReportRelevant(compliance)) return FailedReturnStage.reportFail;
  if (returnToStoreRelevant(compliance)) return FailedReturnStage.returnToStore;
  if (returnPending(detail: detail, deliveryState: deliveryState)) {
    return FailedReturnStage.returnPending;
  }
  return FailedReturnStage.notRelevant;
}

/// True when any failed/return surface is relevant (the entry-point gate).
bool failedReturnRelevant({
  required List<DriverComplianceAction> compliance,
  DriverAssignmentDetail? detail,
  DriverDeliveryState? deliveryState,
}) =>
    failedReturnStage(
      compliance: compliance,
      detail: detail,
      deliveryState: deliveryState,
    ) !=
    FailedReturnStage.notRelevant;
