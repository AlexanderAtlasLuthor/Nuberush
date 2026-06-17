// NubeRush Driver — assignment list view state (Dr.1.3.F).

import '../domain/driver_assignment.dart';

enum AssignmentListStatus {
  initial,
  loading,
  loaded,
  empty,
  unauthenticated,
  error,
  offline,
}

class AssignmentListState {
  const AssignmentListState({
    this.status = AssignmentListStatus.initial,
    this.assignments = const <DriverAssignmentSummary>[],
    this.errorMessage,
  });

  final AssignmentListStatus status;
  final List<DriverAssignmentSummary> assignments;
  final String? errorMessage;
}
