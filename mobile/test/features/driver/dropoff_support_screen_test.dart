// Dr.1.5.G — Dropoff / Compliance dedicated screens tests. Fake repo only.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/dropoff_support_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentDetail startedDetail({String status = 'started'}) =>
    DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: status,
      store: const DriverAssignmentStore(
        id: 's-1',
        name: 'Test Store',
        code: 'TS1',
        timezone: 'UTC',
      ),
    );

DriverDeliveryState stateAt(String s) =>
    DriverDeliveryState(id: 'ds-1', assignmentId: 'a-1', orderId: 'o-1', state: s);

FakeDriverRepository repoAt(String deliveryState, {String status = 'started'}) =>
    FakeDriverRepository(
      detail: startedDetail(status: status),
      deliveryState: stateAt(deliveryState),
    );

void main() {
  Widget dropoffApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: DropoffSupportScreen(controller: c));
  Widget detailApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  Future<void> openStep(WidgetTester tester, String entryKey) async {
    final f = find.byKey(Key(entryKey));
    await tester.ensureVisible(f);
    await tester.pumpAndSettle();
    await tester.tap(f);
    await tester.pumpAndSettle();
  }

  Future<void> tapVisible(WidgetTester tester, Key key) async {
    await tester.ensureVisible(find.byKey(key));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(key));
    await tester.pumpAndSettle();
  }

  // --- Entry point ------------------------------------------------------ //

  testWidgets('detail shows a dropoff entry during the dropoff stage and opens '
      'the dropoff hub; existing groups remain', (tester) async {
    final c = AssignmentDetailController(repoAt('arrived_at_customer'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('dropoff-support-entry'));
    expect(entry, findsOneWidget);
    expect(find.byKey(const Key('assignment-detail-compliance')), findsOneWidget);

    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dropoff-loaded')), findsOneWidget);
  });

  testWidgets('dropoff entry is hidden before the dropoff stage',
      (tester) async {
    final c = AssignmentDetailController(repoAt('en_route_to_store'), 'a-1');
    await tester.pumpWidget(detailApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dropoff-support-entry')), findsNothing);
  });

  // --- Arrival ---------------------------------------------------------- //

  testWidgets('arrival surface uses arrive-customer when available',
      (tester) async {
    final repo = repoAt('picked_up'); // en route -> arrive-customer available
    // picked_up shows depart; use en_route_to_customer for arrive-customer.
    final r2 = repoAt('en_route_to_customer');
    final c = AssignmentDetailController(r2, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dropoff-arrival')), findsOneWidget);

    final detailBefore = r2.detailCalls;
    await tapVisible(tester, const Key('dropoff-arrive-customer'));
    expect(r2.actionCalls['arrive-customer'], 1);
    expect(r2.detailCalls, detailBefore + 1);
    // ignore: unused_local_variable
    final _ = repo;
  });

  // --- Age verification (verify-age payload) --------------------------- //

  testWidgets('age verification reuses verify-age and submits outcome=pass',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();

    await openStep(tester, 'dropoff-step-verify-age');
    expect(find.byKey(const Key('age-verification-screen')), findsOneWidget);

    // Submit disabled until 21+ confirmation is checked.
    await tapVisible(tester, const Key('age-21-confirm'));
    await tapVisible(tester, const Key('age-verify-submit'));

    expect(repo.actionCalls['verify-age'], 1);
    final body = repo.complianceBodies['verify-age']! as Map;
    expect(body['outcome'], 'pass');
    expect(body['age_over_21_confirmed'], true);
    // On success it returns to the hub.
    expect(find.byKey(const Key('dropoff-loaded')), findsOneWidget);
  });

  testWidgets('age verification failure stays on screen with inline error',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    repo.actionError = const ApiError(status: 422, message: 'Gate failed');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();

    await openStep(tester, 'dropoff-step-verify-age');
    await tapVisible(tester, const Key('age-21-confirm'));
    await tapVisible(tester, const Key('age-verify-submit'));

    expect(find.byKey(const Key('age-verification-screen')), findsOneWidget);
    expect(find.byKey(const Key('age-action-error')), findsOneWidget);
    expect(find.text('Gate failed'), findsOneWidget);
  });

  // --- Failure path (fail payload; never return-to-store) -------------- //

  testWidgets('failure path reuses fail and never calls return-to-store',
      (tester) async {
    final repo = repoAt('arrived_at_customer');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();

    // Reachable from the "can't verify age" link on the verify screen.
    await openStep(tester, 'dropoff-step-verify-age');
    await tapVisible(tester, const Key('age-cant-verify'));
    expect(
        find.byKey(const Key('age-verification-failed-screen')), findsOneWidget);

    await tapVisible(tester, const Key('dropoff-fail-submit'));
    // Confirmation dialog -> confirm.
    await tapVisible(tester, const Key('dropoff-fail-confirm'));

    expect(repo.actionCalls['fail'], 1);
    expect(repo.actionCalls['return-to-store'], isNull);
    final body = repo.complianceBodies['fail']! as Map;
    expect(body.containsKey('reason_code'), isTrue);
  });

  // --- Proof ------------------------------------------------------------ //

  testWidgets('proof screen reuses the proof payload (three confirmations)',
      (tester) async {
    final repo = repoAt('id_verified');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();

    await openStep(tester, 'dropoff-step-proof');
    expect(find.byKey(const Key('proof-of-delivery-screen')), findsOneWidget);

    await tapVisible(tester, const Key('dropoff-proof-recipient'));
    await tapVisible(tester, const Key('dropoff-proof-handoff'));
    await tapVisible(tester, const Key('dropoff-proof-unattended'));
    await tapVisible(tester, const Key('dropoff-proof-submit'));

    expect(repo.actionCalls['proof'], 1);
    final body = repo.complianceBodies['proof']! as Map;
    expect(body['recipient_present_confirmed'], true);
    expect(body['handoff_confirmed'], true);
    expect(body['restricted_not_left_unattended'], true);
  });

  // --- Complete --------------------------------------------------------- //

  testWidgets('complete screen submits the bodyless complete action',
      (tester) async {
    final repo = repoAt('id_verified');
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();

    await openStep(tester, 'dropoff-step-complete');
    expect(find.byKey(const Key('complete-delivery-screen')), findsOneWidget);

    await tapVisible(tester, const Key('dropoff-complete-submit'));
    expect(repo.actionCalls['complete'], 1);
    expect(repo.complianceBodies['complete'], isNull);
  });

  // --- Completed summary ------------------------------------------------ //

  testWidgets('completed summary renders only when backend state is completed',
      (tester) async {
    final repo = FakeDriverRepository(
      detail: startedDetail(status: 'completed'),
      deliveryState: stateAt('delivery_completed'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dropoff-completed-summary')), findsOneWidget);
    // No compliance step entries once completed.
    expect(find.byKey(const Key('dropoff-step-complete')), findsNothing);
  });

  // --- Safety / boundary ------------------------------------------------ //

  testWidgets('401 on load surfaces the unauthenticated state', (tester) async {
    final repo = FakeDriverRepository(
      detailError: const ApiError(status: 401, message: 'Not authenticated'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('dropoff-unauthenticated')), findsOneWidget);
  });

  testWidgets('no customer PII is shown on the dropoff hub', (tester) async {
    final c = AssignmentDetailController(repoAt('arrived_at_customer'), 'a-1');
    await tester.pumpWidget(dropoffApp(c));
    await tester.pumpAndSettle();
    // Only safe summary fields; no address/phone/name/coordinates surfaced.
    expect(find.textContaining('phone'), findsNothing);
    expect(find.textContaining('Address'), findsNothing);
    expect(find.textContaining('DOB'), findsNothing);
  });
}
