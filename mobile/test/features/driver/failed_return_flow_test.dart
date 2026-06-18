// Dr.1.5.H — Failed Delivery / Return UX tests. Fake repo only; no backend.
//
// Covers the entry point gating, the dedicated failed-delivery reason screen,
// the return-required / return-to-store action surfaces, and the pending
// store-confirmation surface. Asserts the thin-client boundary: mobile uses only
// the existing `fail` and `return-to-store` actions, never store-side
// confirm-driver-return, order cancel, or inventory release, and shows no PII.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/failed_delivery_reason_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/return_pending_confirmation_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/return_required_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/return_to_store_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentDetail startedDetail({
  String status = 'started',
  DriverAssignmentOrder? order,
}) =>
    DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: status,
      order: order,
      store: const DriverAssignmentStore(
        id: 's-1',
        name: 'Test Store',
        code: 'TS1',
        timezone: 'UTC',
      ),
    );

DriverDeliveryState stateAt(String s) => DriverDeliveryState(
    id: 'ds-1', assignmentId: 'a-1', orderId: 'o-1', state: s);

FakeDriverRepository repoAt(
  String deliveryState, {
  String status = 'started',
  DriverAssignmentOrder? order,
}) =>
    FakeDriverRepository(
      detail: startedDetail(status: status, order: order),
      deliveryState: stateAt(deliveryState),
    );

void main() {
  Widget detailApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));
  Widget failApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: FailedDeliveryReasonScreen(controller: c));
  Widget returnReqApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: ReturnRequiredScreen(controller: c));
  Widget returnStoreApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: ReturnToStoreScreen(controller: c));
  Widget pendingApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: ReturnPendingConfirmationScreen(controller: c));

  Future<void> tapVisible(WidgetTester tester, Key key) async {
    final finder = find.byKey(key);
    // Lazy ListViews may not have built a bottom widget yet — scroll it in.
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(
        finder,
        200,
        scrollable: find.byType(Scrollable).first,
      );
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  Future<void> selectReason(WidgetTester tester, String label) async {
    await tapVisible(tester, const Key('failed-delivery-reason'));
    await tester.tap(find.text(label).last);
    await tester.pumpAndSettle();
  }

  // --- Entry point gating ---------------------------------------------- //

  testWidgets('entry renders when fail is relevant and opens the flow; '
      'existing groups remain', (tester) async {
    final c = AssignmentDetailController(repoAt('arrived_at_customer'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('failed-return-entry'));
    expect(entry, findsOneWidget);
    // Existing compliance group is preserved.
    expect(find.byKey(const Key('assignment-detail-compliance')),
        findsOneWidget);

    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failed-return-loaded')), findsOneWidget);
    expect(find.byKey(const Key('failed-return-step-fail')), findsOneWidget);
  });

  testWidgets('entry renders when return-to-store is relevant', (tester) async {
    final c = AssignmentDetailController(repoAt('delivery_failed'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failed-return-entry')), findsOneWidget);

    await tapVisible(tester, const Key('failed-return-entry'));
    expect(find.byKey(const Key('failed-return-step-return')), findsOneWidget);
  });

  testWidgets('entry renders for a returned/pending state', (tester) async {
    final c = AssignmentDetailController(repoAt('returned_to_store'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failed-return-entry')), findsOneWidget);

    await tapVisible(tester, const Key('failed-return-entry'));
    expect(find.byKey(const Key('failed-return-step-pending')), findsOneWidget);
  });

  testWidgets('entry is hidden when fail/return are not relevant',
      (tester) async {
    final c = AssignmentDetailController(repoAt('en_route_to_store'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failed-return-entry')), findsNothing);
  });

  // --- FailedDeliveryReasonScreen -------------------------------------- //

  testWidgets('failed-delivery screen requires a reason before submitting',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(failApp(c));
    await tester.pumpAndSettle();

    // No reason chosen yet -> submit is disabled and tapping does nothing.
    await tapVisible(tester, const Key('failed-delivery-submit'));
    expect(find.byKey(const Key('failed-delivery-confirm')), findsNothing);
    expect(repo.actionCalls['fail'], isNull);
  });

  testWidgets('failed-delivery submits the existing fail payload and refreshes',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(failApp(c));
    await tester.pumpAndSettle();
    final detailBefore = repo.detailCalls;

    await selectReason(tester, 'Customer unavailable');
    await tapVisible(tester, const Key('failed-delivery-submit'));
    // Confirmation gate.
    await tapVisible(tester, const Key('failed-delivery-confirm'));

    expect(repo.actionCalls['fail'], 1);
    expect(repo.actionCalls['return-to-store'], isNull);
    final body = repo.complianceBodies['fail']! as Map;
    expect(body['reason_code'], 'customer_unavailable');
    // Safe GET refresh ran after success.
    expect(repo.detailCalls, detailBefore + 1);
  });

  testWidgets('failed-delivery is unavailable and disabled off-stage',
      (tester) async {
    final repo = repoAt('en_route_to_store'); // fail not offered here
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(failApp(c));
    await tester.pumpAndSettle();
    expect(
        find.byKey(const Key('failed-delivery-unavailable')), findsOneWidget);

    await selectReason(tester, 'Customer unavailable');
    await tapVisible(tester, const Key('failed-delivery-submit'));
    expect(find.byKey(const Key('failed-delivery-confirm')), findsNothing);
    expect(repo.actionCalls['fail'], isNull);
  });

  testWidgets('failed-delivery failure is inline and non-destructive',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    repo.actionError = const ApiError(status: 422, message: 'Cannot fail now');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(failApp(c));
    await tester.pumpAndSettle();

    await selectReason(tester, 'Customer unavailable');
    await tapVisible(tester, const Key('failed-delivery-submit'));
    await tapVisible(tester, const Key('failed-delivery-confirm'));

    // Stays on screen with an inline error; no navigation, no fake success.
    expect(find.byKey(const Key('failed-delivery-reason-screen')),
        findsOneWidget);
    expect(
        find.byKey(const Key('failed-delivery-action-error')), findsOneWidget);
    expect(find.text('Cannot fail now'), findsOneWidget);
  });

  // --- ReturnRequiredScreen -------------------------------------------- //

  testWidgets('return-required renders backend-authority copy and routes',
      (tester) async {
    final c = AssignmentDetailController(repoAt('delivery_failed'), 'a-1');
    await tester.pumpWidget(returnReqApp(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('return-required-screen')), findsOneWidget);
    expect(find.textContaining('final return confirmation'), findsWidgets);

    await tapVisible(tester, const Key('return-required-continue'));
    expect(find.byKey(const Key('return-to-store-screen')), findsOneWidget);
  });

  // --- ReturnToStoreScreen --------------------------------------------- //

  testWidgets('return-to-store starts the return when delivery_failed',
      (tester) async {
    final repo = repoAt('delivery_failed');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(returnStoreApp(c));
    await tester.pumpAndSettle();
    final detailBefore = repo.detailCalls;

    await tapVisible(tester, const Key('return-to-store-submit'));
    await tapVisible(tester, const Key('return-to-store-confirm'));

    expect(repo.actionCalls['return-to-store'], 1);
    final body = repo.complianceBodies['return-to-store']! as Map;
    expect(body['action'], 'start');
    expect(repo.detailCalls, detailBefore + 1);
  });

  testWidgets('return-to-store marks arrival when returning_to_store',
      (tester) async {
    final repo = repoAt('returning_to_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(returnStoreApp(c));
    await tester.pumpAndSettle();

    await tapVisible(tester, const Key('return-to-store-submit'));
    await tapVisible(tester, const Key('return-to-store-confirm'));

    expect(repo.actionCalls['return-to-store'], 1);
    final body = repo.complianceBodies['return-to-store']! as Map;
    expect(body['action'], 'arrive');
  });

  testWidgets('return-to-store is unavailable and disabled off-stage',
      (tester) async {
    final repo = repoAt('en_route_to_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(returnStoreApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('return-to-store-unavailable')), findsOneWidget);

    await tapVisible(tester, const Key('return-to-store-submit'));
    expect(find.byKey(const Key('return-to-store-confirm')), findsNothing);
    expect(repo.actionCalls['return-to-store'], isNull);
  });

  testWidgets('return-to-store failure is inline and non-destructive',
      (tester) async {
    final repo = repoAt('delivery_failed');
    repo.actionError = const ApiError(status: 409, message: 'Return blocked');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(returnStoreApp(c));
    await tester.pumpAndSettle();

    await tapVisible(tester, const Key('return-to-store-submit'));
    await tapVisible(tester, const Key('return-to-store-confirm'));

    expect(find.byKey(const Key('return-to-store-screen')), findsOneWidget);
    expect(
        find.byKey(const Key('return-to-store-action-error')), findsOneWidget);
    expect(find.text('Return blocked'), findsOneWidget);
  });

  // --- ReturnPendingConfirmationScreen --------------------------------- //

  testWidgets('return-pending renders for returned_to_store and submits nothing',
      (tester) async {
    final repo = repoAt('returned_to_store');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pendingApp(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('return-pending-screen')), findsOneWidget);
    expect(find.textContaining('store / NubeRush'), findsWidgets);
    // No action of any kind was submitted from the pending surface.
    expect(repo.actionCalls.isEmpty, isTrue);
  });

  testWidgets('return-pending renders for a returned order status',
      (tester) async {
    final repo = repoAt(
      'delivery_failed',
      order: const DriverAssignmentOrder(id: 'o-1', status: 'returned'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(pendingApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('return-pending-screen')), findsOneWidget);
  });

  // --- Boundary / safety ------------------------------------------------ //

  testWidgets('no forbidden actions are ever called across the flow',
      (tester) async {
    final repo = repoAt('delivery_failed');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(returnStoreApp(c));
    await tester.pumpAndSettle();
    await tapVisible(tester, const Key('return-to-store-submit'));
    await tapVisible(tester, const Key('return-to-store-confirm'));

    // Only the allowed return-to-store action was used; nothing store-side.
    expect(repo.actionCalls['confirm-driver-return'], isNull);
    expect(repo.actionCalls['cancel'], isNull);
    expect(repo.actionCalls['release-inventory'], isNull);
    expect(repo.actionCalls.keys, contains('return-to-store'));
  });

  testWidgets('no customer PII / address / coordinates appear in the flow',
      (tester) async {
    final c = AssignmentDetailController(repoAt('delivery_failed'), 'a-1');
    await tester.pumpWidget(returnReqApp(c));
    await tester.pumpAndSettle();
    expect(find.textContaining('Address'), findsNothing);
    expect(find.textContaining('phone'), findsNothing);
    expect(find.textContaining('DOB'), findsNothing);
    expect(find.textContaining('Latitude'), findsNothing);
    expect(find.textContaining('Longitude'), findsNothing);
    expect(find.textContaining('coordinates'), findsNothing);
  });

  testWidgets('401 on load surfaces the unauthenticated state in the hub',
      (tester) async {
    final repo = FakeDriverRepository(
      detailError: const ApiError(status: 401, message: 'Not authenticated'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assignment-detail-unauthenticated')),
        findsOneWidget);
  });
}
