// Dr.1.3.F — AssignmentListController state-mapping tests. Fake repo, no net.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_list_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_list_state.dart';

import 'fake_driver_repository.dart';

void main() {
  test('initial state before load', () {
    final c = AssignmentListController(FakeDriverRepository());
    expect(c.state.status, AssignmentListStatus.initial);
  });

  test('loading then loaded with assignments', () async {
    final c = AssignmentListController(FakeDriverRepository());
    final seen = <AssignmentListStatus>[];
    c.addListener(() => seen.add(c.state.status));
    await c.load();
    expect(seen.first, AssignmentListStatus.loading);
    expect(c.state.status, AssignmentListStatus.loaded);
    expect(c.state.assignments, isNotEmpty);
  });

  test('empty list -> empty state', () async {
    final c = AssignmentListController(FakeDriverRepository(assignments: []));
    await c.load();
    expect(c.state.status, AssignmentListStatus.empty);
  });

  test('error -> error state', () async {
    final c = AssignmentListController(
      FakeDriverRepository(
        assignmentsError: const ApiError(status: 500, message: 'Server error'),
      ),
    );
    await c.load();
    expect(c.state.status, AssignmentListStatus.error);
    expect(c.state.errorMessage, 'Server error');
  });

  test('network (status 0) -> offline state', () async {
    final c = AssignmentListController(
      FakeDriverRepository(assignmentsError: ApiError.network()),
    );
    await c.load();
    expect(c.state.status, AssignmentListStatus.offline);
  });

  test('401 -> unauthenticated state', () async {
    final c = AssignmentListController(
      FakeDriverRepository(
        assignmentsError:
            const ApiError(status: 401, message: 'Not authenticated'),
      ),
    );
    await c.load();
    expect(c.state.status, AssignmentListStatus.unauthenticated);
  });

  test('retry recovers from offline to loaded', () async {
    final repo = FakeDriverRepository(assignmentsError: ApiError.network());
    final c = AssignmentListController(repo);
    await c.load();
    expect(c.state.status, AssignmentListStatus.offline);
    repo.assignmentsError = null;
    await c.retry();
    expect(c.state.status, AssignmentListStatus.loaded);
    expect(repo.assignmentsCalls, 2);
  });
}
