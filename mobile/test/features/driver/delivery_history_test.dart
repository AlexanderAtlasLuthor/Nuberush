// Dr.1.5.K — Delivery history surface tests. Fake repo only; no backend.
//
// History is built only from GET /driver/assignments?status=<terminal>. These
// tests assert the safe GET filters, the loading/empty/loaded/error states,
// filter switching, retry, PII-free cards, and safe detail navigation.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/presentation/delivery_history_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/delivery_history_screen.dart';

import 'fake_driver_repository.dart';

DriverAssignmentSummary terminalSummary({
  String id = 'h-1',
  String status = 'completed',
  String? store = 'Test Store',
  String? orderStatus = 'delivered',
}) =>
    DriverAssignmentSummary(
      id: id,
      orderId: 'o-1',
      storeId: 's-1',
      status: status,
      storeName: store,
      orderStatus: orderStatus,
    );

void main() {
  Widget historyApp(
    DeliveryHistoryController c, {
    void Function(BuildContext, DriverAssignmentSummary)? onOpen,
  }) =>
      NubeRushDriverApp(
        home: DeliveryHistoryScreen(controller: c, onOpenAssignment: onOpen),
      );

  Future<void> tapVisible(WidgetTester tester, Key key) async {
    final finder = find.byKey(key);
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(finder, 200,
          scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  testWidgets('loads completed history with a safe status GET', (tester) async {
    final repo = FakeDriverRepository(
      assignments: <DriverAssignmentSummary>[terminalSummary()],
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));

    // Initial frame shows loading before the post-frame load resolves.
    expect(find.byKey(const Key('history-loading')), findsOneWidget);

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('history-loaded')), findsOneWidget);
    expect(find.byKey(const Key('history-card-h-1')), findsOneWidget);
    // Default filter is completed -> exactly one safe status GET.
    expect(repo.assignmentsStatusFilters, <String?>['completed']);
  });

  testWidgets('empty state renders when no terminal assignments',
      (tester) async {
    final repo = FakeDriverRepository(
      assignments: <DriverAssignmentSummary>[],
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('history-empty')), findsOneWidget);
  });

  testWidgets('switching a filter chip sends the matching safe status GET',
      (tester) async {
    final repo = FakeDriverRepository(
      assignments: <DriverAssignmentSummary>[terminalSummary()],
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));
    await tester.pumpAndSettle();
    expect(repo.assignmentsStatusFilters, <String?>['completed']);

    await tapVisible(tester, const Key('history-filter-canceled'));
    expect(repo.assignmentsStatusFilters, <String?>['completed', 'canceled']);

    await tapVisible(tester, const Key('history-filter-declined'));
    expect(repo.assignmentsStatusFilters,
        <String?>['completed', 'canceled', 'declined']);

    await tapVisible(tester, const Key('history-filter-expired'));
    expect(repo.assignmentsStatusFilters,
        <String?>['completed', 'canceled', 'declined', 'expired']);

    // Never a null (no-status) filter, never a non-terminal value.
    expect(repo.assignmentsStatusFilters.contains(null), isFalse);
  });

  testWidgets('error state retry re-runs only a safe status GET',
      (tester) async {
    final repo = FakeDriverRepository(
      assignmentsError: const ApiError(status: 500, message: 'Server error'),
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('history-error')), findsOneWidget);

    // Fix the backend then retry.
    repo.assignmentsError = null;
    repo.assignments = <DriverAssignmentSummary>[terminalSummary()];
    await tapVisible(tester, const Key('history-retry'));

    expect(find.byKey(const Key('history-loaded')), findsOneWidget);
    // Retry re-ran the SAME terminal filter via a safe GET; no actions.
    expect(repo.assignmentsStatusFilters, <String?>['completed', 'completed']);
    expect(repo.actionCalls, isEmpty);
  });

  testWidgets('401 surfaces the unauthenticated state', (tester) async {
    final repo = FakeDriverRepository(
      assignmentsError: const ApiError(status: 401, message: 'Not auth'),
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('history-unauthenticated')), findsOneWidget);
  });

  testWidgets('cards show no customer PII / earnings / payouts', (tester) async {
    final repo = FakeDriverRepository(
      assignments: <DriverAssignmentSummary>[terminalSummary()],
    );
    final c = DeliveryHistoryController(repo);
    await tester.pumpWidget(historyApp(c));
    await tester.pumpAndSettle();

    expect(find.textContaining('Address'), findsNothing);
    expect(find.textContaining('phone'), findsNothing);
    expect(find.textContaining('DOB'), findsNothing);
    expect(find.textContaining('Latitude'), findsNothing);
    expect(find.textContaining('Longitude'), findsNothing);
    expect(find.textContaining('Earnings'), findsNothing);
    expect(find.textContaining('Payout'), findsNothing);
    expect(find.textContaining('Tip'), findsNothing);
    expect(find.textContaining('Tax'), findsNothing);
  });

  testWidgets('detail navigation reuses the injected safe callback',
      (tester) async {
    final repo = FakeDriverRepository(
      assignments: <DriverAssignmentSummary>[terminalSummary()],
    );
    final c = DeliveryHistoryController(repo);
    DriverAssignmentSummary? opened;
    await tester.pumpWidget(historyApp(c, onOpen: (_, a) => opened = a));
    await tester.pumpAndSettle();

    await tapVisible(tester, const Key('history-card-h-1'));
    expect(opened?.id, 'h-1');
    // Navigation made no extra backend list call beyond the initial load.
    expect(repo.assignmentsStatusFilters, <String?>['completed']);
  });
}
