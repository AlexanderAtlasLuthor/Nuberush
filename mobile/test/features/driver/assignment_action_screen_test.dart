// Dr.1.3.G — operational action UI tests on the assignment detail screen.
// Fake repo only; no backend/Supabase.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';

import 'fake_driver_repository.dart';

// Compliance labels that must NEVER appear as buttons in Dr.1.3.G.
const _forbiddenComplianceLabels = <String>[
  'Verify age',
  'Verify Age',
  'Proof of Delivery',
  'Complete delivery',
  'Complete',
  'Failed delivery',
  'Fail Delivery',
  'Return to Store',
  'Confirm driver return',
  'Confirm Return',
];

DriverAssignmentDetail offeredDetail() => const DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: 'offered',
    );

void main() {
  Widget app(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  testWidgets('offered assignment shows Accept + Decline buttons',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('assignment-detail-actions')), findsOneWidget);
    expect(find.byKey(const Key('action-accept')), findsOneWidget);
    expect(find.byKey(const Key('action-decline')), findsOneWidget);
    expect(find.text('Accept'), findsOneWidget);
    expect(find.text('Decline'), findsOneWidget);
  });

  testWidgets('started + en_route_to_store shows Arrive at store',
      (tester) async {
    // Default sampleDetail status 'started' + sampleDeliveryState
    // 'en_route_to_store'.
    final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('action-arrive-store')), findsOneWidget);
    expect(find.text('Arrive at store'), findsOneWidget);
  });

  testWidgets('tapping Accept invokes the repository and refreshes',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    final detailCallsBefore = repo.detailCalls;
    await tester.tap(find.byKey(const Key('action-accept')));
    await tester.pumpAndSettle();

    expect(repo.actionCalls['accept'], 1);
    expect(repo.detailCalls, detailCallsBefore + 1); // refreshed
  });

  testWidgets('Decline shows a confirmation dialog; confirm invokes',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('action-decline')));
    await tester.pumpAndSettle();
    // Dialog visible.
    expect(find.byKey(const Key('action-confirm')), findsOneWidget);

    await tester.tap(find.byKey(const Key('action-confirm')));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['decline'], 1);
  });

  testWidgets('Decline cancel does NOT invoke the action', (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('action-decline')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(repo.actionCalls['decline'], isNull);
  });

  testWidgets(
      'Dr.1.3.I: a failing action shows an inline error and keeps detail',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await tester.tap(find.byKey(const Key('action-accept')));
    await tester.pumpAndSettle();

    // Non-destructive: the loaded detail stays, an inline error card appears,
    // and the full-screen error state is NOT shown.
    expect(find.byKey(const Key('assignment-detail-loaded')), findsOneWidget);
    expect(find.byKey(const Key('assignment-detail-action-error')),
        findsOneWidget);
    expect(find.byKey(const Key('assignment-detail-error')), findsNothing);
    expect(find.text('Already accepted'), findsOneWidget);
    // The action buttons are still present (detail not replaced).
    expect(find.byKey(const Key('action-accept')), findsOneWidget);
  });

  testWidgets('Dr.1.3.I: dismiss clears the inline action error card',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await tester.tap(find.byKey(const Key('action-accept')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assignment-detail-action-error')),
        findsOneWidget);

    await tester.tap(find.byKey(const Key('action-error-dismiss')));
    await tester.pumpAndSettle();
    expect(
        find.byKey(const Key('assignment-detail-action-error')), findsNothing);
    expect(find.byKey(const Key('assignment-detail-loaded')), findsOneWidget);
  });

  testWidgets('Dr.1.3.I: reload on the inline error re-fetches GET only',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    repo.actionError = const ApiError(status: 409, message: 'Already accepted');
    await tester.tap(find.byKey(const Key('action-accept')));
    await tester.pumpAndSettle();

    final acceptCalls = repo.actionCalls['accept'];
    final detailBefore = repo.detailCalls;
    repo.actionError = null;

    await tester.tap(find.byKey(const Key('action-error-reload')));
    await tester.pumpAndSettle();

    expect(repo.detailCalls, detailBefore + 1); // GET refresh ran
    expect(repo.actionCalls['accept'], acceptCalls); // mutation NOT repeated
    expect(
        find.byKey(const Key('assignment-detail-action-error')), findsNothing);
  });

  testWidgets(
      'Dr.1.3.I: active action shows a spinner and disables all buttons',
      (tester) async {
    final repo = FakeDriverRepository(detail: offeredDetail());
    repo.actionGate = Completer<void>();
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('action-accept')));
    await tester.pump(); // start the action; gate keeps it in flight

    // The active action shows a spinner.
    expect(
      find.descendant(
        of: find.byKey(const Key('action-accept')),
        matching: find.byType(CircularProgressIndicator),
      ),
      findsOneWidget,
    );
    // Every action button is disabled while one action runs.
    final accept =
        tester.widget<FilledButton>(find.byKey(const Key('action-accept')));
    final decline =
        tester.widget<FilledButton>(find.byKey(const Key('action-decline')));
    expect(accept.onPressed, isNull);
    expect(decline.onPressed, isNull);

    repo.actionGate!.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('no compliance buttons appear in the actions card',
      (tester) async {
    final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    for (final label in _forbiddenComplianceLabels) {
      expect(find.widgetWithText(FilledButton, label), findsNothing);
      expect(find.widgetWithText(ElevatedButton, label), findsNothing);
      expect(find.widgetWithText(TextButton, label), findsNothing);
    }
  });
}
