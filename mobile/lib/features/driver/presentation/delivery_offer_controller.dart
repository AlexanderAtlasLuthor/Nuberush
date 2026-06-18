// NubeRush Driver — Delivery Offer Surface controller (Dr.1.5.D).
//
// Loads assignments via the existing read repository and filters to the
// offered ones (status == 'offered'). Accept/decline use the existing
// bodyless endpoints; on success the controller re-reads GET /driver/assignments
// (so an accepted/declined offer drops out of the offered-only list). There is
// no polling, no stream, no realtime, no expiry, no optimistic local mutation.
//
// Error policy mirrors the assignment-detail hardening (Dr.1.3.I):
//   - initial-load failure (no loaded data) -> full-screen error/offline/unauth
//   - action failure with the list loaded     -> non-destructive inline error
//   - 401 anywhere                             -> full-screen unauthenticated

import 'package:flutter/foundation.dart';

import '../../../core/api/api_error.dart';
import '../data/driver_repository.dart';
import '../domain/driver_assignment.dart';
import 'delivery_offer_state.dart';

class DeliveryOfferController extends ChangeNotifier {
  DeliveryOfferController(this._repository);

  final DriverReadRepository _repository;

  DeliveryOfferState _state = const DeliveryOfferState();
  DeliveryOfferState get state => _state;

  void _set(DeliveryOfferState next) {
    _state = next;
    notifyListeners();
  }

  /// Fetch assignments and keep only the offered ones.
  Future<void> load() async {
    _set(const DeliveryOfferState(status: DeliveryOfferStatus.loading));
    try {
      final offers = _filterOffered(await _repository.fetchAssignments());
      _set(DeliveryOfferState(
        status: offers.isEmpty
            ? DeliveryOfferStatus.empty
            : DeliveryOfferStatus.loaded,
        offers: offers,
      ));
    } on ApiError catch (error) {
      _set(_mapError(error));
    }
  }

  Future<void> retry() => load();

  /// GET-only refresh used by the inline action-error banner. Never repeats a
  /// failed mutation.
  Future<void> reload() => load();

  /// Dismiss the inline action error without re-fetching.
  void clearActionError() {
    if (!_state.hasActionError) return;
    _set(_state.copyWith(clearActionError: true));
  }

  /// Accept an offer (existing bodyless POST .../accept), then re-read.
  Future<void> accept(String assignmentId) =>
      _runAction(assignmentId, OfferAction.accept,
          (repo) => repo.acceptAssignment(assignmentId));

  /// Decline an offer (existing bodyless POST .../decline), then re-read. No
  /// request body is sent — the backend receives the decline action only.
  Future<void> decline(String assignmentId) =>
      _runAction(assignmentId, OfferAction.decline,
          (repo) => repo.declineAssignment(assignmentId));

  Future<void> _runAction(
    String assignmentId,
    OfferAction action,
    Future<void> Function(DriverReadRepository repo) call,
  ) async {
    // One action at a time; only act when a loaded list is on screen.
    if (_state.isActionInFlight) return;
    if (_state.status != DeliveryOfferStatus.loaded) return;

    _set(_state.copyWith(
      runningOfferId: assignmentId,
      runningAction: action,
      clearActionError: true,
    ));
    try {
      await call(_repository);
      // Success: re-read authoritative state. load() rebuilds fresh state,
      // clearing the running action and any inline error, and re-filters so the
      // accepted/declined offer disappears if its status changed.
      await load();
    } on ApiError catch (error) {
      _handleActionError(error);
    }
  }

  void _handleActionError(ApiError error) {
    // Session no longer valid: full-screen unauthenticated.
    if (error.status == 401) {
      _set(_mapError(error));
      return;
    }
    // Keep the loaded offer list visible; surface a non-destructive inline
    // error and clear the running action.
    if (_state.status == DeliveryOfferStatus.loaded) {
      _set(_state.copyWith(
        clearRunning: true,
        actionErrorMessage: _safeActionMessage(error),
        actionErrorIsOffline: error.status == 0,
      ));
      return;
    }
    _set(_mapError(error));
  }

  List<DriverAssignmentSummary> _filterOffered(
    List<DriverAssignmentSummary> assignments,
  ) =>
      assignments
          .where((a) => a.status == kOfferedStatus)
          .toList(growable: false);

  DeliveryOfferState _mapError(ApiError error) {
    final DeliveryOfferStatus status;
    if (error.status == 0) {
      status = DeliveryOfferStatus.offline;
    } else if (error.status == 401) {
      status = DeliveryOfferStatus.unauthenticated;
    } else {
      status = DeliveryOfferStatus.error;
    }
    return DeliveryOfferState(
      status: status,
      errorMessage: _safeFullScreenMessage(error),
    );
  }

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
