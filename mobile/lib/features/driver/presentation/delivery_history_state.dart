// NubeRush Driver — delivery history view state (Dr.1.5.K).
//
// History is built strictly from `GET /driver/assignments?status=<terminal>`.
// The terminal filters mirror the backend's existing assignment `status` query
// values; no unsupported status is invented.

import '../domain/driver_assignment.dart';

enum DeliveryHistoryStatus {
  initial,
  loading,
  loaded,
  empty,
  unauthenticated,
  error,
  offline,
}

/// Terminal assignment status filters used for history. Wire values match the
/// backend's existing `status` query param (terminal lifecycle values).
enum HistoryFilter { completed, canceled, declined, expired }

extension HistoryFilterX on HistoryFilter {
  /// Backend query value for `?status=`.
  String get wire => switch (this) {
        HistoryFilter.completed => 'completed',
        HistoryFilter.canceled => 'canceled',
        HistoryFilter.declined => 'declined',
        HistoryFilter.expired => 'expired',
      };

  String get label => switch (this) {
        HistoryFilter.completed => 'Completed',
        HistoryFilter.canceled => 'Canceled',
        HistoryFilter.declined => 'Declined',
        HistoryFilter.expired => 'Expired',
      };
}

class DeliveryHistoryState {
  const DeliveryHistoryState({
    this.status = DeliveryHistoryStatus.initial,
    this.filter = HistoryFilter.completed,
    this.assignments = const <DriverAssignmentSummary>[],
    this.errorMessage,
  });

  final DeliveryHistoryStatus status;
  final HistoryFilter filter;
  final List<DriverAssignmentSummary> assignments;
  final String? errorMessage;
}
