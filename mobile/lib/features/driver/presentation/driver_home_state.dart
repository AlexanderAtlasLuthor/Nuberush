// NubeRush Driver — Driver Home view state (Dr.1.3.E).

import '../domain/driver_eligibility.dart';
import '../domain/driver_profile.dart';

/// Lifecycle of the read-only Driver Home surface.
enum DriverHomeStatus {
  initial,
  loading,
  loaded,
  unauthenticated,
  error,
  offline,
}

/// Immutable view state for the Driver Home/Profile/Eligibility screen.
class DriverHomeState {
  const DriverHomeState({
    this.status = DriverHomeStatus.initial,
    this.profile,
    this.eligibility,
    this.errorMessage,
  });

  final DriverHomeStatus status;
  final DriverProfile? profile;
  final DriverEligibility? eligibility;
  final String? errorMessage;

  bool get isLoading => status == DriverHomeStatus.loading;
  bool get isLoaded => status == DriverHomeStatus.loaded;
  bool get isOffline => status == DriverHomeStatus.offline;
  bool get isError => status == DriverHomeStatus.error;
  bool get isUnauthenticated => status == DriverHomeStatus.unauthenticated;
}
