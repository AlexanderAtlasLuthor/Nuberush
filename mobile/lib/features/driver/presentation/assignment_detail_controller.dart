// NubeRush Driver — assignment detail controller (Dr.1.3.F + .G + .H + .I).
//
// Loads assignment detail then its delivery operational state, runs operational
// (G) and compliance (H) actions, and maps transport outcomes to view states.
// No transitions are computed locally, no optimistic mutation, no polling.
//
// Dr.1.3.I hardening: an action failure on an already-loaded screen no longer
// blows away the loaded detail. The detail/delivery-state stay visible and a
// non-destructive inline action error is surfaced instead. Full-screen
// error/offline/unauthenticated states remain for initial-load (no loaded data)
// failures, and 401 always falls to unauthenticated because the session is no
// longer valid.

import 'package:flutter/foundation.dart';

import '../../../core/api/api_error.dart';
import '../data/driver_repository.dart';
import '../domain/compliance_requests.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';

class AssignmentDetailController extends ChangeNotifier {
  AssignmentDetailController(this._repository, this.assignmentId);

  final DriverReadRepository _repository;
  final String assignmentId;

  AssignmentDetailState _state = const AssignmentDetailState();
  AssignmentDetailState get state => _state;

  void _set(AssignmentDetailState next) {
    _state = next;
    notifyListeners();
  }

  Future<void> load() async {
    _set(const AssignmentDetailState(status: AssignmentDetailStatus.loading));
    try {
      final detail = await _repository.fetchAssignmentDetail(assignmentId);
      final deliveryState = await _repository.fetchDeliveryState(assignmentId);
      _set(AssignmentDetailState(
        status: AssignmentDetailStatus.loaded,
        detail: detail,
        deliveryState: deliveryState,
      ));
    } on ApiError catch (error) {
      _set(_mapError(error));
    }
  }

  /// Explicit reload after an initial-load failure (full-screen retry).
  Future<void> retry() => load();

  /// GET-only refresh used by the inline action-error banner (Dr.1.3.I). It
  /// re-fetches detail + delivery-state and NEVER repeats the failed mutation.
  /// The fresh state load() builds clears any stale inline action error.
  Future<void> reload() => load();

  /// Dismiss the inline action error without re-fetching. No-op if none shown.
  void clearActionError() {
    if (!_state.hasActionError) return;
    _set(_state.copyWith(clearActionError: true));
  }

  /// Execute an operational action (Dr.1.3.G), then re-read the authoritative
  /// detail + delivery-state. No optimistic local transition is applied.
  ///
  /// Duplicate-tap safe: ignored if an action is already in flight or the
  /// screen is not in the loaded state.
  Future<void> runAction(DriverOperationalAction action) async {
    if (_state.isActionInFlight) return;
    if (_state.status != AssignmentDetailStatus.loaded) return;

    // Per-action loading feedback; keep the loaded detail visible and clear any
    // prior inline action error.
    _set(_state.copyWith(runningAction: action, clearActionError: true));
    try {
      await action.invoke(_repository, assignmentId);
      // Success: re-read backend state. load() rebuilds fresh state, which
      // also clears runningAction and any action error.
      await load();
    } on ApiError catch (error) {
      _handleActionError(error);
    }
  }

  // --- Compliance actions (Dr.1.3.H) ---------------------------------- //
  // Same guarantees as runAction: per-action loading, in-flight/loaded guard,
  // re-read on success, safe error handling, no optimistic local transition,
  // no local order/inventory mutation. The repository attaches a fresh
  // Idempotency-Key per attempt.

  Future<void> verifyAge(VerifyAgeRequest request) => _runCompliance(
        DriverComplianceAction.verifyAge,
        (repo) => repo.verifyAge(assignmentId, request),
      );

  Future<void> submitProof(ProofRequest request) => _runCompliance(
        DriverComplianceAction.submitProof,
        (repo) => repo.submitProof(assignmentId, request),
      );

  Future<void> completeDelivery() => _runCompliance(
        DriverComplianceAction.completeDelivery,
        (repo) => repo.completeDelivery(assignmentId),
      );

  Future<void> failDelivery(FailRequest request) => _runCompliance(
        DriverComplianceAction.reportFailedDelivery,
        (repo) => repo.failDelivery(assignmentId, request),
      );

  Future<void> returnToStore(ReturnToStoreRequest request) => _runCompliance(
        DriverComplianceAction.returnToStore,
        (repo) => repo.returnToStore(assignmentId, request),
      );

  Future<void> _runCompliance(
    DriverComplianceAction action,
    Future<void> Function(DriverReadRepository repo) call,
  ) async {
    if (_state.isActionInFlight) return;
    if (_state.status != AssignmentDetailStatus.loaded) return;

    _set(_state.copyWith(
      runningComplianceAction: action,
      clearActionError: true,
    ));
    try {
      await call(_repository);
      // Success: re-read authoritative backend state (clears running action
      // and any inline action error).
      await load();
    } on ApiError catch (error) {
      _handleActionError(error);
    }
  }

  /// Dr.1.3.I action-failure mapping. Non-destructive when loaded data exists.
  void _handleActionError(ApiError error) {
    // Session no longer valid: drop to the full-screen unauthenticated state
    // even when detail was loaded — the loaded view is no longer trustworthy.
    if (error.status == 401) {
      _set(_mapError(error));
      return;
    }
    // Loaded data present: keep detail + delivery-state visible and surface a
    // non-destructive inline action error. The running action is cleared.
    if (_state.status == AssignmentDetailStatus.loaded && _state.detail != null) {
      _set(_state.copyWith(
        clearRunningAction: true,
        actionErrorMessage: _safeActionMessage(error),
        actionErrorIsOffline: error.status == 0,
      ));
      return;
    }
    // No loaded data to preserve: fall back to the full-screen state.
    _set(_mapError(error));
  }

  /// Full-screen state mapping for load/reload (no loaded data) failures.
  AssignmentDetailState _mapError(ApiError error) {
    final AssignmentDetailStatus status;
    if (error.status == 0) {
      status = AssignmentDetailStatus.offline;
    } else if (error.status == 401) {
      status = AssignmentDetailStatus.unauthenticated;
    } else {
      status = AssignmentDetailStatus.error;
    }
    return AssignmentDetailState(
      status: status,
      errorMessage: _safeFullScreenMessage(error),
    );
  }

  /// Inline action-error copy. Offline gets a connection-oriented message; an
  /// empty/null backend message falls back to a generic safe message.
  static String _safeActionMessage(ApiError error) {
    if (error.status == 0) {
      return 'Network unavailable. Your action was not submitted — '
          'check your connection and try again.';
    }
    final message = error.message.trim();
    if (message.isEmpty) {
      return 'That action could not be completed. Please try again.';
    }
    return message;
  }

  /// Full-screen copy with a safe fallback when the backend message is empty.
  static String _safeFullScreenMessage(ApiError error) {
    if (error.status == 0) {
      return 'Network unavailable. Check your connection and try again.';
    }
    final message = error.message.trim();
    if (message.isEmpty) {
      return 'Something went wrong. Please try again.';
    }
    return message;
  }
}
