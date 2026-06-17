// NubeRush Driver — assignment detail view state (Dr.1.3.F + .G + .H + .I).

import '../domain/driver_assignment.dart';
import '../domain/driver_delivery_state.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';

enum AssignmentDetailStatus {
  initial,
  loading,
  loaded,
  unauthenticated,
  error,
  offline,
}

class AssignmentDetailState {
  const AssignmentDetailState({
    this.status = AssignmentDetailStatus.initial,
    this.detail,
    this.deliveryState,
    this.errorMessage,
    this.runningAction,
    this.runningComplianceAction,
    this.actionErrorMessage,
    this.actionErrorIsOffline = false,
  });

  final AssignmentDetailStatus status;
  final DriverAssignmentDetail? detail;
  final DriverDeliveryState? deliveryState;

  /// Full-screen error copy, shown only for `error`/`offline`/`unauthenticated`
  /// statuses (initial-load or explicit-reload failures with no loaded data).
  final String? errorMessage;

  /// The operational action currently in flight (Dr.1.3.G), or null. Used for
  /// per-action loading feedback and duplicate-tap prevention. Set only while
  /// [status] is [AssignmentDetailStatus.loaded].
  final DriverOperationalAction? runningAction;

  /// The compliance action currently in flight (Dr.1.3.H), or null.
  final DriverComplianceAction? runningComplianceAction;

  /// Dr.1.3.I: non-destructive inline action-error message. Present only while
  /// [status] is [AssignmentDetailStatus.loaded] and a previous action failed
  /// without invalidating the loaded view (any status other than 401). The
  /// already-loaded [detail]/[deliveryState] stay visible alongside it.
  final String? actionErrorMessage;

  /// True when [actionErrorMessage] came from a status-0 (network) failure, so
  /// the UI can show offline-flavoured copy/iconography.
  final bool actionErrorIsOffline;

  /// True while ANY action (operational or compliance) is in flight.
  bool get isActionInFlight =>
      runningAction != null || runningComplianceAction != null;

  /// Invariant guard: an operational and a compliance action can never be in
  /// flight simultaneously (the single in-flight guard prevents starting one
  /// while the other runs).
  bool get hasMutuallyExclusiveRunningActions =>
      runningAction == null || runningComplianceAction == null;

  /// True when a non-destructive inline action error is currently shown.
  bool get hasActionError => actionErrorMessage != null;

  AssignmentDetailState copyWith({
    AssignmentDetailStatus? status,
    DriverAssignmentDetail? detail,
    DriverDeliveryState? deliveryState,
    String? errorMessage,
    DriverOperationalAction? runningAction,
    DriverComplianceAction? runningComplianceAction,
    bool clearRunningAction = false,
    String? actionErrorMessage,
    bool? actionErrorIsOffline,
    bool clearActionError = false,
  }) {
    return AssignmentDetailState(
      status: status ?? this.status,
      detail: detail ?? this.detail,
      deliveryState: deliveryState ?? this.deliveryState,
      errorMessage: errorMessage ?? this.errorMessage,
      runningAction:
          clearRunningAction ? null : (runningAction ?? this.runningAction),
      runningComplianceAction: clearRunningAction
          ? null
          : (runningComplianceAction ?? this.runningComplianceAction),
      actionErrorMessage: clearActionError
          ? null
          : (actionErrorMessage ?? this.actionErrorMessage),
      actionErrorIsOffline: clearActionError
          ? false
          : (actionErrorIsOffline ?? this.actionErrorIsOffline),
    );
  }
}
