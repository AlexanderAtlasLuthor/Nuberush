// Dr.1.3.F — AssignmentDetailController state-mapping tests. Fake repo, no net.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_state.dart';

import 'fake_driver_repository.dart';

void main() {
  test('initial state before load', () {
    final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
    expect(c.state.status, AssignmentDetailStatus.initial);
  });

  test('loading then loaded with detail + delivery state', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    final seen = <AssignmentDetailStatus>[];
    c.addListener(() => seen.add(c.state.status));
    await c.load();
    expect(seen.first, AssignmentDetailStatus.loading);
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.detail, isNotNull);
    expect(c.state.deliveryState, isNotNull);
    expect(repo.detailCalls, 1);
    expect(repo.deliveryStateCalls, 1);
  });

  test('detail error -> error state', () async {
    final c = AssignmentDetailController(
      FakeDriverRepository(
        detailError: const ApiError(status: 404, message: 'Not found'),
      ),
      'a-1',
    );
    await c.load();
    expect(c.state.status, AssignmentDetailStatus.error);
    expect(c.state.errorMessage, 'Not found');
  });

  test('delivery-state error -> error state', () async {
    final c = AssignmentDetailController(
      FakeDriverRepository(
        deliveryStateError: const ApiError(status: 500, message: 'Boom'),
      ),
      'a-1',
    );
    await c.load();
    expect(c.state.status, AssignmentDetailStatus.error);
  });

  test('network (status 0) -> offline state', () async {
    final c = AssignmentDetailController(
      FakeDriverRepository(detailError: ApiError.network()),
      'a-1',
    );
    await c.load();
    expect(c.state.status, AssignmentDetailStatus.offline);
  });

  test('401 -> unauthenticated state', () async {
    final c = AssignmentDetailController(
      FakeDriverRepository(
        detailError: const ApiError(status: 401, message: 'Not authenticated'),
      ),
      'a-1',
    );
    await c.load();
    expect(c.state.status, AssignmentDetailStatus.unauthenticated);
  });

  test('retry recovers from offline to loaded', () async {
    final repo = FakeDriverRepository(detailError: ApiError.network());
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    expect(c.state.status, AssignmentDetailStatus.offline);
    repo.detailError = null;
    await c.retry();
    expect(c.state.status, AssignmentDetailStatus.loaded);
  });
}
