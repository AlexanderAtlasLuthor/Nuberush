// NubeRush Driver — delivery history controller (Dr.1.5.K).
//
// Read-only. Loads terminal assignment summaries via the EXISTING
// `GET /driver/assignments?status=<terminal>` filter and maps transport
// outcomes to view states. It never calls /orders/*, builds no fake history,
// computes no lifecycle, and runs no polling/timer. The backend is the
// authority; this only presents what the assignments list returns.

import 'package:flutter/foundation.dart';

import '../../../core/api/api_error.dart';
import '../data/driver_repository.dart';
import 'delivery_history_state.dart';

class DeliveryHistoryController extends ChangeNotifier {
  DeliveryHistoryController(this._repository);

  final DriverReadRepository _repository;

  DeliveryHistoryState _state = const DeliveryHistoryState();
  DeliveryHistoryState get state => _state;

  void _set(DeliveryHistoryState next) {
    _state = next;
    notifyListeners();
  }

  /// Load history for [filter] (defaults to the current filter). Safe GET only.
  Future<void> load([HistoryFilter? filter]) async {
    final f = filter ?? _state.filter;
    _set(DeliveryHistoryState(
      status: DeliveryHistoryStatus.loading,
      filter: f,
    ));
    try {
      final assignments = await _repository.fetchAssignments(status: f.wire);
      _set(DeliveryHistoryState(
        status: assignments.isEmpty
            ? DeliveryHistoryStatus.empty
            : DeliveryHistoryStatus.loaded,
        filter: f,
        assignments: assignments,
      ));
    } on ApiError catch (error) {
      _set(_mapError(error, f));
    }
  }

  /// Switch the active terminal filter and reload (safe GET only).
  Future<void> selectFilter(HistoryFilter filter) => load(filter);

  /// Retry the current filter (safe GET only).
  Future<void> retry() => load();

  DeliveryHistoryState _mapError(ApiError error, HistoryFilter filter) {
    final DeliveryHistoryStatus status;
    if (error.status == 0) {
      status = DeliveryHistoryStatus.offline;
    } else if (error.status == 401) {
      status = DeliveryHistoryStatus.unauthenticated;
    } else {
      status = DeliveryHistoryStatus.error;
    }
    return DeliveryHistoryState(
      status: status,
      filter: filter,
      errorMessage: error.message,
    );
  }
}
