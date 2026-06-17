// NubeRush Driver — assignment list controller (Dr.1.3.F).
//
// Read-only: loads assignment summaries and maps transport outcomes to view
// states. No accept/decline/start, no polling, no mutation.

import 'package:flutter/foundation.dart';

import '../../../core/api/api_error.dart';
import '../data/driver_repository.dart';
import 'assignment_list_state.dart';

class AssignmentListController extends ChangeNotifier {
  AssignmentListController(this._repository);

  final DriverReadRepository _repository;

  AssignmentListState _state = const AssignmentListState();
  AssignmentListState get state => _state;

  void _set(AssignmentListState next) {
    _state = next;
    notifyListeners();
  }

  Future<void> load() async {
    _set(const AssignmentListState(status: AssignmentListStatus.loading));
    try {
      final assignments = await _repository.fetchAssignments();
      _set(AssignmentListState(
        status: assignments.isEmpty
            ? AssignmentListStatus.empty
            : AssignmentListStatus.loaded,
        assignments: assignments,
      ));
    } on ApiError catch (error) {
      _set(_mapError(error));
    }
  }

  Future<void> retry() => load();

  AssignmentListState _mapError(ApiError error) {
    final AssignmentListStatus status;
    if (error.status == 0) {
      status = AssignmentListStatus.offline;
    } else if (error.status == 401) {
      status = AssignmentListStatus.unauthenticated;
    } else {
      status = AssignmentListStatus.error;
    }
    return AssignmentListState(status: status, errorMessage: error.message);
  }
}
