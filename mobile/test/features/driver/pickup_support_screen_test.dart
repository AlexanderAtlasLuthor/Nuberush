// Dr.1.5.F — Pickup Support Screens tests. Fake repo, no network/Supabase.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/core/ui/nuberush_primary_button.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/pickup_checklist.dart';
import 'package:nuberush_driver/features/driver/presentation/pickup_support_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentDetail startedDetail() => const DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: 'started',
      store: DriverAssignmentStore(
        id: 's-1',
        name: 'Test Store',
        code: 'TS1',
        timezone: 'UTC',
      ),
    );

DriverDeliveryState stateAt(String s) =>
    DriverDeliveryState(id: 'ds-1', assignmentId: 'a-1', orderId: 'o-1', state: s);

FakeDriverRepository repoAt(String deliveryState) => FakeDriverRepository(
      detail: startedDetail(),
      deliveryState: stateAt(deliveryState),
    );

void main() {
  Widget pickupApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: PickupSupportScreen(controller: c));
  Widget detailApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  Future<void> checkAll(WidgetTester tester) async {
    for (var i = 0; i < kPickupChecklistItems.length; i++) {
      final box = find.byKey(Key('pickup-check-$i'));
      await tester.ensureVisible(box);
      await tester.pumpAndSettle();
      await tester.tap(box);
    }
    await tester.pumpAndSettle();
  }

  // --- Entry point from the active delivery detail --------------------- //

  testWidgets('detail shows a pickup entry during the pickup stage and opens '
      'the pickup support screen', (tester) async {
    final c = AssignmentDetailController(repoAt('en_route_to_store'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('pickup-support-entry'));
    expect(entry, findsOneWidget);
    // Existing action group is still present (entry does not replace it).
    expect(find.byKey(const Key('assignment-detail-actions')), findsOneWidget);

    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pickup-loaded')), findsOneWidget);
  });

  testWidgets('pickup entry is hidden when not in the pickup stage',
      (tester) async {
    // en_route_to_customer -> no arrive-store/pickup actions available.
    final c = AssignmentDetailController(repoAt('en_route_to_customer'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pickup-support-entry')), findsNothing);
  });

  // --- Arrival surface -------------------------------------------------- //

  testWidgets('arrival surface renders summary and arrive-store when available',
      (tester) async {
    final c = AssignmentDetailController(repoAt('en_route_to_store'), 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('pickup-summary')), findsOneWidget);
    // Safe store/order/state summary (label + value render as separate Texts).
    expect(find.text('Test Store (TS1)'), findsOneWidget);
    expect(find.text('en_route_to_store'), findsOneWidget);
    expect(find.byKey(const Key('pickup-arrival')), findsOneWidget);
    expect(find.byKey(const Key('pickup-arrive-store')), findsOneWidget);
    // Pickup confirm is not shown yet.
    expect(find.byKey(const Key('pickup-confirm')), findsNothing);
  });

  testWidgets('arrive-store calls the existing action and refreshes',
      (tester) async {
    final repo = repoAt('en_route_to_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    final detailBefore = repo.detailCalls;
    final btn = find.byKey(const Key('pickup-arrive-store'));
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pumpAndSettle();

    expect(repo.actionCalls['arrive-store'], 1);
    expect(repo.detailCalls, detailBefore + 1); // safe GET refresh
  });

  // --- Checklist + confirm ---------------------------------------------- //

  testWidgets('pickup stage shows a display-only checklist; confirm is gated '
      'until all items are checked', (tester) async {
    final c = AssignmentDetailController(repoAt('arrived_at_store'), 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('pickup-checklist')), findsOneWidget);
    expect(find.byKey(const Key('pickup-arrival')), findsNothing);

    // Confirm disabled before the checklist is complete.
    final confirm = find.byKey(const Key('pickup-confirm-pickup'));
    await tester.ensureVisible(confirm);
    await tester.pumpAndSettle();
    expect(
      tester.widget<NubeRushPrimaryButton>(confirm).onPressed,
      isNull,
    );

    await checkAll(tester);
    await tester.ensureVisible(confirm);
    await tester.pumpAndSettle();
    expect(
      tester.widget<NubeRushPrimaryButton>(confirm).onPressed,
      isNotNull,
    );
  });

  testWidgets('confirm pickup calls the existing pickup action and refreshes',
      (tester) async {
    final repo = repoAt('arrived_at_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    await checkAll(tester);
    final detailBefore = repo.detailCalls;
    final confirm = find.byKey(const Key('pickup-confirm-pickup'));
    await tester.ensureVisible(confirm);
    await tester.pumpAndSettle();
    await tester.tap(confirm);
    await tester.pumpAndSettle();

    expect(repo.actionCalls['pickup'], 1);
    expect(repo.detailCalls, detailBefore + 1);
  });

  testWidgets('confirm pickup failure is inline and non-destructive',
      (tester) async {
    final repo = repoAt('arrived_at_store');
    repo.actionError = const ApiError(status: 409, message: 'Not ready');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    await checkAll(tester);
    final confirm = find.byKey(const Key('pickup-confirm-pickup'));
    await tester.ensureVisible(confirm);
    await tester.pumpAndSettle();
    await tester.tap(confirm);
    await tester.pumpAndSettle();

    // Surface stays loaded, inline error shown, no fake success/navigation.
    expect(find.byKey(const Key('pickup-loaded')), findsOneWidget);
    expect(find.byKey(const Key('pickup-action-error')), findsOneWidget);
    expect(find.text('Not ready'), findsOneWidget);
    expect(find.byKey(const Key('pickup-checklist')), findsOneWidget);
  });

  testWidgets('arrive-store failure is inline and non-destructive',
      (tester) async {
    final repo = repoAt('en_route_to_store');
    repo.actionError = const ApiError(status: 500, message: 'Boom');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    final btn = find.byKey(const Key('pickup-arrive-store'));
    await tester.ensureVisible(btn);
    await tester.pumpAndSettle();
    await tester.tap(btn);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('pickup-action-error')), findsOneWidget);
    expect(find.text('Boom'), findsOneWidget);
    expect(find.byKey(const Key('pickup-arrival')), findsOneWidget);
  });

  // --- Not-active fallback + auth ------------------------------------- //

  testWidgets('non-pickup state shows a safe not-active card', (tester) async {
    final c = AssignmentDetailController(repoAt('en_route_to_customer'), 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pickup-not-active')), findsOneWidget);
    expect(find.byKey(const Key('pickup-arrival')), findsNothing);
    expect(find.byKey(const Key('pickup-confirm')), findsNothing);
  });

  testWidgets('401 on load surfaces the unauthenticated state', (tester) async {
    final repo = FakeDriverRepository(
      detailError: const ApiError(status: 401, message: 'Not authenticated'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pickup-unauthenticated')), findsOneWidget);
  });

  // --- Issue info (informational only) --------------------------------- //

  testWidgets('pickup issue entry opens static, informational guidance',
      (tester) async {
    final repo = repoAt('arrived_at_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('pickup-issue-entry'));
    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('pickup-issue-info')), findsOneWidget);
    expect(find.byKey(const Key('pickup-issue-back')), findsOneWidget);
    // Informational only: it triggered no driver action of any kind.
    expect(repo.actionCalls, isEmpty);

    await tester.tap(find.byKey(const Key('pickup-issue-back')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('pickup-loaded')), findsOneWidget);
  });

  // --- Checklist is display-only --------------------------------------- //

  testWidgets('checking the checklist triggers no repository calls',
      (tester) async {
    final repo = repoAt('arrived_at_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pickupApp(c));
    await tester.pumpAndSettle();

    await checkAll(tester);
    // No action submitted simply by completing the local checklist.
    expect(repo.actionCalls, isEmpty);
  });
}
