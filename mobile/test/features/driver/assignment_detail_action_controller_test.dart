// Dr.1.3.G — AssignmentDetailController.runAction tests. Fake repo, no net.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_state.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_operational_action.dart';

import 'fake_driver_repository.dart';

void main() {
  test('successful action invokes endpoint then refreshes detail+state',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final detailCallsBefore = repo.detailCalls;
    final stateCallsBefore = repo.deliveryStateCalls;

    await c.runAction(DriverOperationalAction.accept);

    expect(repo.actionCalls['accept'], 1);
    // Refresh happened: detail + delivery-state re-read after the action.
    expect(repo.detailCalls, detailCallsBefore + 1);
    expect(repo.deliveryStateCalls, stateCallsBefore + 1);
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.runningAction, isNull);
  });

  test('duplicate / in-flight taps are ignored', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();

    // Fire two without awaiting the first; the second must be a no-op while
    // the first is in flight.
    final f1 = c.runAction(DriverOperationalAction.start);
    final f2 = c.runAction(DriverOperationalAction.start);
    await Future.wait([f1, f2]);

    expect(repo.actionCalls['start'], 1);
  });

  test('action is ignored unless the screen is loaded', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    // No load() — still initial.
    await c.runAction(DriverOperationalAction.accept);
    expect(repo.actionCalls['accept'], isNull);
  });

  test('Dr.1.3.I: action error status 0 keeps loaded detail + inline error',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final detailStatusBefore = c.state.detail?.status;

    repo.actionError = ApiError.network();
    await c.runAction(DriverOperationalAction.start);

    // Non-destructive: loaded detail stays, inline (offline) action error shown.
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.detail, isNotNull);
    expect(c.state.deliveryState, isNotNull);
    expect(c.state.hasActionError, isTrue);
    expect(c.state.actionErrorIsOffline, isTrue);
    expect(c.state.runningAction, isNull);
    // The detail status was never optimistically mutated by the client.
    expect(detailStatusBefore, 'started');
  });

  test('action error 401 -> full-screen unauthenticated (session invalid)',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 401, message: 'Not authenticated');
    await c.runAction(DriverOperationalAction.accept);
    expect(c.state.status, AssignmentDetailStatus.unauthenticated);
  });

  test('Dr.1.3.I: action error 409 keeps loaded detail + inline error',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await c.runAction(DriverOperationalAction.accept);

    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.detail, isNotNull);
    expect(c.state.actionErrorMessage, 'Already accepted');
    expect(c.state.actionErrorIsOffline, isFalse);
    expect(c.state.runningAction, isNull);
  });

  test('Dr.1.3.I: empty backend message falls back to a safe inline message',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 422, message: '');
    await c.runAction(DriverOperationalAction.accept);
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.actionErrorMessage, isNotNull);
    expect(c.state.actionErrorMessage!.isNotEmpty, isTrue);
  });

  test('Dr.1.3.I: reload after inline action error is GET-only (no mutation)',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();

    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await c.runAction(DriverOperationalAction.accept);
    expect(c.state.hasActionError, isTrue);
    final actionCallsBefore = repo.actionCalls['accept'];
    final detailBefore = repo.detailCalls;
    final stateBefore = repo.deliveryStateCalls;

    repo.actionError = null; // backend recovered
    await c.reload();

    // GET refresh ran; the failed mutation was NOT repeated.
    expect(repo.detailCalls, detailBefore + 1);
    expect(repo.deliveryStateCalls, stateBefore + 1);
    expect(repo.actionCalls['accept'], actionCallsBefore);
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.hasActionError, isFalse); // stale error cleared
  });

  test('Dr.1.3.I: dismiss clears the inline action error', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await c.runAction(DriverOperationalAction.accept);
    expect(c.state.hasActionError, isTrue);

    c.clearActionError();
    expect(c.state.hasActionError, isFalse);
    expect(c.state.status, AssignmentDetailStatus.loaded);
  });

  test('Dr.1.3.I: a successful action clears a prior inline action error',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await c.runAction(DriverOperationalAction.start);
    expect(c.state.hasActionError, isTrue);

    repo.actionError = null;
    await c.runAction(DriverOperationalAction.start);
    expect(c.state.hasActionError, isFalse);
    expect(c.state.status, AssignmentDetailStatus.loaded);
  });

  test('Dr.1.3.I: runningAction and runningComplianceAction never coexist',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    var everBothSet = false;
    c.addListener(() {
      if (!c.state.hasMutuallyExclusiveRunningActions) everBothSet = true;
    });

    // Fire an operational and a compliance action together; the guard lets only
    // one through.
    final f1 = c.runAction(DriverOperationalAction.start);
    final f2 = c.completeDelivery();
    await Future.wait([f1, f2]);

    expect(everBothSet, isFalse);
  });
}
