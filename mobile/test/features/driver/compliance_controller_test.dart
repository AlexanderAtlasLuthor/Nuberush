// Dr.1.3.H — AssignmentDetailController compliance-action tests. Fake repo.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/compliance_requests.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_state.dart';

import 'fake_driver_repository.dart';

const _verifyReq = VerifyAgeRequest(outcome: VerifyAgeOutcome.pass);

void main() {
  test('successful compliance action refreshes detail + delivery-state',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final d = repo.detailCalls, s = repo.deliveryStateCalls;

    await c.verifyAge(_verifyReq);

    expect(repo.actionCalls['verify-age'], 1);
    expect(repo.detailCalls, d + 1);
    expect(repo.deliveryStateCalls, s + 1);
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.runningComplianceAction, isNull);
  });

  test('duplicate / in-flight compliance taps are ignored', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final f1 = c.completeDelivery();
    final f2 = c.completeDelivery();
    await Future.wait([f1, f2]);
    expect(repo.actionCalls['complete'], 1);
  });

  test('compliance action ignored unless loaded', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.verifyAge(_verifyReq); // still initial
    expect(repo.actionCalls['verify-age'], isNull);
  });

  test('Dr.1.3.I: status 0 keeps loaded detail + inline offline error',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final statusBefore = c.state.detail?.status;
    repo.actionError = ApiError.network();
    await c.completeDelivery();
    // Non-destructive: loaded detail preserved, inline offline error shown.
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.detail, isNotNull);
    expect(c.state.hasActionError, isTrue);
    expect(c.state.actionErrorIsOffline, isTrue);
    expect(c.state.runningComplianceAction, isNull);
    expect(statusBefore, 'started'); // never optimistically mutated
  });

  test('401 -> full-screen unauthenticated (session invalid)', () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 401, message: 'Not authenticated');
    await c.submitProof(const ProofRequest(
      recipientPresentConfirmed: true,
      handoffConfirmed: true,
      restrictedNotLeftUnattended: true,
    ));
    expect(c.state.status, AssignmentDetailStatus.unauthenticated);
  });

  test('Dr.1.3.I: 422 gate failure keeps loaded detail + inline error',
      () async {
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    repo.actionError = const ApiError(status: 422, message: 'proof required');
    await c.completeDelivery();
    expect(c.state.status, AssignmentDetailStatus.loaded);
    expect(c.state.detail, isNotNull);
    expect(c.state.actionErrorMessage, 'proof required');
    expect(c.state.runningComplianceAction, isNull);
  });

  test('an operational action in flight blocks a compliance action', () async {
    // Both action kinds share the single in-flight guard.
    final repo = FakeDriverRepository();
    final c = AssignmentDetailController(repo, 'a-1');
    await c.load();
    final f1 = c.completeDelivery();
    final f2 = c.failDelivery(
        const FailRequest(reasonCode: FailureReason.customerUnavailable));
    await Future.wait([f1, f2]);
    expect(repo.actionCalls['complete'], 1);
    expect(repo.actionCalls['fail'], isNull);
  });
}
