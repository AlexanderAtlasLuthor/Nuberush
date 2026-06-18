// Dr.1.5.E — Active Delivery Overview + Timeline tests. Fake repo, no network.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/compliance_status_card.dart';
import 'package:nuberush_driver/features/driver/presentation/delivery_timeline.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_compliance_action.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_operational_action.dart';
import 'package:nuberush_driver/features/driver/presentation/next_action_panel.dart';

import 'fake_driver_repository.dart';

DriverAssignmentDetail startedDetail() => const DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: 'started',
    );

DriverDeliveryState stateAt(String s) =>
    DriverDeliveryState(id: 'ds-1', assignmentId: 'a-1', orderId: 'o-1', state: s);

void main() {
  Widget app(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  Widget host(Widget child) =>
      NubeRushDriverApp(home: Scaffold(body: SingleChildScrollView(child: child)));

  // --- Pure timeline builder ------------------------------------------- //

  group('buildDeliveryTimeline', () {
    test('known state marks done/current/upcoming correctly', () {
      final view = buildDeliveryTimeline('picked_up'); // canonical index 3
      expect(view.hasException, isFalse);
      expect(view.steps[0].status, TimelineStepStatus.done);
      expect(view.steps[3].label, 'Picked up');
      expect(view.steps[3].status, TimelineStepStatus.current);
      expect(view.steps[4].status, TimelineStepStatus.upcoming);
    });

    test('completed marks the last step current and no false exception', () {
      final view = buildDeliveryTimeline('delivery_completed');
      expect(view.hasException, isFalse);
      expect(view.steps.last.status, TimelineStepStatus.current);
    });

    test('null/empty state yields a safe waiting fallback', () {
      final view = buildDeliveryTimeline(null);
      expect(view.exceptionLabel, 'Waiting for delivery state');
      expect(view.steps.every((s) => s.status == TimelineStepStatus.upcoming),
          isTrue);
    });

    test('terminal states yield an exception label, never false completion',
        () {
      expect(buildDeliveryTimeline('delivery_failed').exceptionLabel,
          'Delivery failed');
      expect(buildDeliveryTimeline('returning_to_store').exceptionLabel,
          'Returning to store');
      expect(buildDeliveryTimeline('returned_to_store').exceptionLabel,
          'Returned to store');
      expect(buildDeliveryTimeline('canceled').exceptionLabel, 'Canceled');
      // None of these claim a completed step.
      for (final s in ['delivery_failed', 'returning_to_store', 'canceled']) {
        final view = buildDeliveryTimeline(s);
        expect(view.steps.any((x) => x.status == TimelineStepStatus.done),
            isFalse);
      }
    });

    test('unknown state renders a safe fallback echoing the raw state', () {
      final view = buildDeliveryTimeline('some_new_backend_state');
      expect(view.exceptionLabel, 'Current state: some_new_backend_state');
    });
  });

  // --- Timeline widget -------------------------------------------------- //

  testWidgets('timeline highlights the current step for a known state',
      (tester) async {
    await tester.pumpWidget(host(const DeliveryTimeline(state: 'picked_up')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('delivery-timeline')), findsOneWidget);
    expect(find.byKey(const Key('delivery-timeline-current')), findsOneWidget);
    expect(find.byKey(const Key('delivery-timeline-exception')), findsNothing);
  });

  testWidgets('timeline shows a safe fallback for an unknown state',
      (tester) async {
    await tester.pumpWidget(host(const DeliveryTimeline(state: 'mystery')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('delivery-timeline-exception')), findsOneWidget);
    expect(find.text('Current state: mystery'), findsOneWidget);
    // No step is marked current for an unknown state.
    expect(find.byKey(const Key('delivery-timeline-current')), findsNothing);
  });

  // --- Next action panel ------------------------------------------------ //

  testWidgets('next action panel suggests an operational action', (tester) async {
    await tester.pumpWidget(host(const NextActionPanel(
      operationalActions: [DriverOperationalAction.arriveStore],
      complianceActions: [],
    )));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('next-action-suggestion')), findsOneWidget);
    expect(find.text('Suggested: Arrive at store'), findsOneWidget);
  });

  testWidgets('next action panel suggests a compliance action when no '
      'operational action exists', (tester) async {
    await tester.pumpWidget(host(const NextActionPanel(
      operationalActions: [],
      complianceActions: [DriverComplianceAction.verifyAge],
    )));
    await tester.pumpAndSettle();
    expect(find.text('Suggested: Verify age'), findsOneWidget);
  });

  testWidgets('next action panel shows a safe fallback when no action exists',
      (tester) async {
    await tester.pumpWidget(host(const NextActionPanel(
      operationalActions: [],
      complianceActions: [],
    )));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('next-action-none')), findsOneWidget);
    expect(find.text('No driver action available right now.'), findsOneWidget);
  });

  // --- Compliance status card ------------------------------------------ //

  testWidgets('compliance status reflects availability without claiming '
      'completion', (tester) async {
    await tester.pumpWidget(host(const ComplianceStatusCard(
      complianceActions: [
        DriverComplianceAction.verifyAge,
        DriverComplianceAction.reportFailedDelivery,
      ],
    )));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('compliance-status-card')), findsOneWidget);
    expect(find.text('Age verification'), findsOneWidget);
    // Available rows + locked rows both render; nothing claims "verified".
    expect(find.text('Available now'), findsWidgets);
    expect(find.text('Locked'), findsWidgets);
    expect(find.textContaining('verified'), findsNothing);
  });

  // --- Detail-screen integration --------------------------------------- //

  testWidgets('assignment detail renders the active delivery overview',
      (tester) async {
    final repo = FakeDriverRepository(
      detail: startedDetail(),
      deliveryState: stateAt('en_route_to_store'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('active-delivery-summary')), findsOneWidget);
    expect(find.byKey(const Key('delivery-timeline')), findsOneWidget);
    expect(find.byKey(const Key('next-action-panel')), findsOneWidget);
    expect(find.byKey(const Key('compliance-status-card')), findsOneWidget);
    // Backend-reported strings preserved (display-only).
    expect(find.text('Status: started'), findsOneWidget);
    expect(find.text('State: en_route_to_store'), findsOneWidget);
    // The existing operational action group is still present.
    expect(find.byKey(const Key('assignment-detail-actions')), findsOneWidget);
  });

  testWidgets('overview renders safely for an unknown delivery state',
      (tester) async {
    final repo = FakeDriverRepository(
      detail: startedDetail(),
      deliveryState: stateAt('totally_unknown'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('assignment-detail-loaded')), findsOneWidget);
    expect(find.byKey(const Key('delivery-timeline-exception')), findsOneWidget);
    // Unknown state offers no operational action — safe no-action copy.
    expect(find.byKey(const Key('next-action-none')), findsOneWidget);
  });

  testWidgets('summary card renders timestamps that exist on the model',
      (tester) async {
    final detail = DriverAssignmentDetail(
      id: 'a-1',
      orderId: 'o-1',
      storeId: 's-1',
      status: 'completed',
      acceptedAt: DateTime.utc(2026, 6, 18, 14, 30),
      completedAt: DateTime.utc(2026, 6, 18, 15, 5),
    );
    final repo = FakeDriverRepository(
      detail: detail,
      deliveryState: stateAt('delivery_completed'),
    );
    final c = AssignmentDetailController(repo, 'a-1');
    await tester.pumpWidget(app(c));
    await tester.pumpAndSettle();
    expect(find.textContaining('Accepted: '), findsOneWidget);
    expect(find.textContaining('Completed: '), findsOneWidget);
  });
}
