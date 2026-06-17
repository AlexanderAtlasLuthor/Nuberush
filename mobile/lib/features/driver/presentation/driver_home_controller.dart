// NubeRush Driver — Driver Home controller (Dr.1.3.E).
//
// A minimal ChangeNotifier (no state-management package) that loads the
// read-only profile + eligibility and maps transport outcomes to view states:
//   - ApiError.status == 0   -> offline (retryable)
//   - ApiError.status == 401 -> unauthenticated
//   - other ApiError         -> error
// No action buttons, no assignment navigation, no background polling.

import 'package:flutter/foundation.dart';

import '../../../core/api/api_error.dart';
import '../data/driver_repository.dart';
import 'driver_home_state.dart';

class DriverHomeController extends ChangeNotifier {
  DriverHomeController(this._repository);

  final DriverReadRepository _repository;

  DriverHomeState _state = const DriverHomeState();
  DriverHomeState get state => _state;

  void _set(DriverHomeState next) {
    _state = next;
    notifyListeners();
  }

  /// Load profile then eligibility. Either failure maps to a single view state.
  Future<void> load() async {
    _set(const DriverHomeState(status: DriverHomeStatus.loading));
    try {
      final profile = await _repository.fetchDriverProfile();
      final eligibility = await _repository.fetchDriverEligibility();
      _set(DriverHomeState(
        status: DriverHomeStatus.loaded,
        profile: profile,
        eligibility: eligibility,
      ));
    } on ApiError catch (error) {
      _set(_mapError(error));
    }
  }

  /// Re-run [load] (used by the offline/error retry affordance).
  Future<void> retry() => load();

  DriverHomeState _mapError(ApiError error) {
    final DriverHomeStatus status;
    if (error.status == 0) {
      status = DriverHomeStatus.offline;
    } else if (error.status == 401) {
      status = DriverHomeStatus.unauthenticated;
    } else {
      status = DriverHomeStatus.error;
    }
    return DriverHomeState(status: status, errorMessage: error.message);
  }
}
