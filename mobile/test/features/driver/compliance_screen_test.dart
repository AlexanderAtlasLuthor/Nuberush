// Dr.1.3.H — compliance action UI tests on the assignment detail screen.
// Fake repo only; no backend/Supabase.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentDetail startedDetail() => const DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: 'started',
    );

DriverDeliveryState stateAt(String s) =>
    DriverDeliveryState(id: 'ds-1', assignmentId: 'a-1', orderId: 'o-1', state: s);

FakeDriverRepository repoAt(String deliveryState) => FakeDriverRepository(
      detail: startedDetail(),
      deliveryState: stateAt(deliveryState),
    );

void main() {
  Widget app(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  testWidgets('arrived_at_customer shows the compliance group + verify/fail',
      (tester) async {
    final c = AssignmentDetailController(repoAt('arrived_at_customer'), 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    expect(
        find.byKey(const Key('assignment-detail-compliance')), findsOneWidget);
    expect(find.byKey(const Key('compliance-verify-age')), findsOneWidget);
    expect(find.byKey(const Key('compliance-fail')), findsOneWidget);
  });

  testWidgets('verify-age flow submits outcome=pass', (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('compliance-verify-age')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('verify-age-dialog')), findsOneWidget);

    await tester.tap(find.byKey(const Key('verify-age-submit')));
    await tester.pumpAndSettle();

    expect(repo.actionCalls['verify-age'], 1);
    expect((repo.complianceBodies['verify-age']! as Map)['outcome'], 'pass');
  });

  testWidgets('proof flow requires all three confirmations then submits',
      (tester) async {
    final repo = repoAt('id_verified');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('compliance-proof')));
    await tester.pumpAndSettle();

    // Submit is disabled until all three are checked.
    final submit = tester.widget<FilledButton>(
      find.byKey(const Key('proof-submit')),
    );
    expect(submit.onPressed, isNull);

    await tester.tap(find.byKey(const Key('proof-recipient')));
    await tester.tap(find.byKey(const Key('proof-handoff')));
    await tester.tap(find.byKey(const Key('proof-unattended')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('proof-submit')));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['proof'], 1);
  });

  testWidgets('complete flow confirms then submits (bodyless)', (tester) async {
    final repo = repoAt('id_verified');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('compliance-complete')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('complete-confirm')));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['complete'], 1);
    expect(repo.complianceBodies['complete'], isNull);
  });

  testWidgets('fail flow submits a reason code', (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('compliance-fail')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('fail-submit')));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['fail'], 1);
    expect(
      (repo.complianceBodies['fail']! as Map).containsKey('reason_code'),
      isTrue,
    );
  });

  testWidgets('return-to-store at delivery_failed submits action=start',
      (tester) async {
    final repo = repoAt('delivery_failed');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('compliance-return-to-store')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('return-confirm')));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['return-to-store'], 1);
    expect((repo.complianceBodies['return-to-store']! as Map)['action'],
        'start');
  });

  testWidgets(
      'Dr.1.3.I: failing compliance action shows inline error, keeps detail',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    repo.actionError = const ApiError(status: 500, message: 'Boom');
    await tester.tap(find.byKey(const Key('compliance-verify-age')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('verify-age-submit')));
    await tester.pumpAndSettle();

    // Non-destructive: inline error card, loaded view + compliance group stay,
    // and the full-screen error state is NOT shown.
    expect(find.byKey(const Key('assignment-detail-action-error')),
        findsOneWidget);
    expect(find.byKey(const Key('assignment-detail-error')), findsNothing);
    expect(
        find.byKey(const Key('assignment-detail-compliance')), findsOneWidget);
    expect(find.text('Boom'), findsOneWidget);
  });

  testWidgets('no store-confirmation / confirm-driver-return button exists',
      (tester) async {
    final c = AssignmentDetailController(repoAt('delivery_failed'), 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('compliance-confirm-driver-return')),
        findsNothing);
    for (final label in const [
      'Confirm driver return',
      'Confirm return',
      'Store confirmation',
    ]) {
      expect(find.text(label), findsNothing);
    }
  });
}
