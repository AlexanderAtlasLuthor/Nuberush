// Dr.1.5.D — Delivery Offer Surface tests. Fake repo, no network/Supabase.
//
// Covers offer filtering (offered-only), loading/empty/error/retry, accept and
// decline via the existing endpoints (decline sends no body), success refresh,
// and non-destructive inline action errors. No realtime/push/expiry exists to
// test — by design.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/presentation/delivery_offer_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/delivery_offer_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentSummary offer(String id, {String store = 'Test Store'}) =>
    DriverAssignmentSummary(
      id: id,
      orderId: 'o-$id',
      storeId: 's-1',
      status: 'offered',
      storeName: store,
      orderStatus: 'pending',
    );

DriverAssignmentSummary nonOffer(String id, String status) =>
    DriverAssignmentSummary(
      id: id,
      orderId: 'o-$id',
      storeId: 's-1',
      status: status,
      storeName: 'Other Store',
      orderStatus: 'pending',
    );

void main() {
  Widget appWith(DeliveryOfferController c) =>
      NubeRushDriverApp(home: DeliveryOfferScreen(controller: c));

  testWidgets('renders only offered assignments as offers', (tester) async {
    final repo = FakeDriverRepository(assignments: [
      offer('a1'),
      nonOffer('a2', 'accepted'),
      offer('a3'),
      nonOffer('a4', 'completed'),
    ]);
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('offers-loaded')), findsOneWidget);
    expect(find.byKey(const Key('offer-card-a1')), findsOneWidget);
    expect(find.byKey(const Key('offer-card-a3')), findsOneWidget);
    // Non-offered assignments never render as offers.
    expect(find.byKey(const Key('offer-card-a2')), findsNothing);
    expect(find.byKey(const Key('offer-card-a4')), findsNothing);
  });

  testWidgets('shows loading then empty when there are no offered assignments',
      (tester) async {
    final repo = FakeDriverRepository(assignments: [
      nonOffer('a2', 'accepted'),
      nonOffer('a4', 'completed'),
    ]);
    final controller = DeliveryOfferController(repo);
    await tester.pumpWidget(appWith(controller));
    expect(find.byKey(const Key('offers-loading')), findsOneWidget);

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offers-empty')), findsOneWidget);
    expect(find.text('No delivery offers right now.'), findsOneWidget);
  });

  testWidgets('error state renders with retry that reloads', (tester) async {
    final repo = FakeDriverRepository(
      assignmentsError: const ApiError(status: 500, message: 'Server error'),
    );
    final controller = DeliveryOfferController(repo);
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offers-error')), findsOneWidget);
    expect(find.text('Server error'), findsOneWidget);

    repo.assignmentsError = null;
    repo.assignments = [offer('a1')];
    await tester.tap(find.byKey(const Key('offers-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offer-card-a1')), findsOneWidget);
  });

  testWidgets('offline state renders retry affordance', (tester) async {
    final repo = FakeDriverRepository(assignmentsError: ApiError.network());
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offers-offline')), findsOneWidget);
    expect(find.byKey(const Key('offers-retry')), findsOneWidget);
  });

  testWidgets('accept calls the existing accept endpoint for that assignment '
      'and refreshes the list', (tester) async {
    final repo = FakeDriverRepository(assignments: [offer('a1'), offer('a3')]);
    repo.actionGate = Completer<void>();
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('offer-accept-a1')));
    await tester.pump();

    // While in flight, the backend has been told to accept a1 (and only a1).
    expect(repo.actionCalls['accept'], 1);
    expect(repo.actionAssignmentIds['accept'], ['a1']);

    // Simulate the backend moving a1 out of the offered pool, then let the
    // action complete so the controller re-reads GET /driver/assignments.
    repo.assignments = [offer('a3')];
    repo.actionGate!.complete();
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('offer-card-a1')), findsNothing);
    expect(find.byKey(const Key('offer-card-a3')), findsOneWidget);
  });

  testWidgets('accept failure keeps the offer list and shows inline error',
      (tester) async {
    final repo = FakeDriverRepository(assignments: [offer('a1')]);
    repo.actionError = const ApiError(status: 500, message: 'Accept failed');
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('offer-accept-a1')));
    await tester.pumpAndSettle();

    // Non-destructive: the offer stays, an inline error is shown.
    expect(find.byKey(const Key('offer-card-a1')), findsOneWidget);
    expect(find.byKey(const Key('offers-action-error')), findsOneWidget);
    expect(find.text('Accept failed'), findsOneWidget);
  });

  testWidgets('decline confirms, calls decline with no body, and refreshes',
      (tester) async {
    final repo = FakeDriverRepository(assignments: [offer('a1')]);
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('offer-decline-a1')));
    await tester.pumpAndSettle();
    // Confirmation dialog appears; decline not yet sent.
    expect(find.byKey(const Key('offer-decline-dialog')), findsOneWidget);
    expect(repo.actionCalls['decline'], isNull);

    repo.assignments = const <DriverAssignmentSummary>[];
    await tester.tap(find.byKey(const Key('offer-decline-confirm')));
    await tester.pumpAndSettle();

    expect(repo.actionCalls['decline'], 1);
    expect(repo.actionAssignmentIds['decline'], ['a1']);
    // Repository signature is bodyless (no payload concept exists to assert).
    expect(find.byKey(const Key('offers-empty')), findsOneWidget);
  });

  testWidgets('decline can be cancelled without calling the endpoint',
      (tester) async {
    final repo = FakeDriverRepository(assignments: [offer('a1')]);
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('offer-decline-a1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(repo.actionCalls['decline'], isNull);
    expect(find.byKey(const Key('offer-card-a1')), findsOneWidget);
  });

  testWidgets('inline action error can be dismissed', (tester) async {
    final repo = FakeDriverRepository(assignments: [offer('a1')]);
    repo.actionError = const ApiError(status: 500, message: 'Accept failed');
    await tester.pumpWidget(appWith(DeliveryOfferController(repo)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('offer-accept-a1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offers-action-error')), findsOneWidget);

    await tester.tap(find.byKey(const Key('offers-action-error-dismiss')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('offers-action-error')), findsNothing);
    expect(find.byKey(const Key('offer-card-a1')), findsOneWidget);
  });
}
