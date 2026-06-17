// Dr.1.3.F — assignment list + detail widget tests. Fake repo, no net/Supabase.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_detail_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_list_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/assignment_list_screen.dart';

import 'fake_driver_repository.dart';

/// Action/compliance button labels that must NEVER appear in read-only F UI.
const _forbiddenActionLabels = <String>[
  'Accept',
  'Decline',
  'Start',
  'Arrive at Store',
  'Pickup',
  'Depart',
  'Arrive at Customer',
  'Verify Age',
  'Proof of Delivery',
  'Complete',
  'Fail Delivery',
  'Return to Store',
  'Confirm Return',
];

void main() {
  Widget listApp(AssignmentListController c) =>
      NubeRushDriverApp(home: AssignmentListScreen(controller: c));
  Widget detailApp(AssignmentDetailController c) =>
      NubeRushDriverApp(home: AssignmentDetailScreen(controller: c));

  group('AssignmentListScreen', () {
    testWidgets('renders loading on the initial frame', (tester) async {
      final c = AssignmentListController(FakeDriverRepository());
      await tester.pumpWidget(listApp(c));
      expect(find.byKey(const Key('assignments-loading')), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('renders loaded assignments', (tester) async {
      final c = AssignmentListController(FakeDriverRepository());
      await tester.pumpWidget(listApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignments-loaded')), findsOneWidget);
      expect(find.text('Test Store'), findsOneWidget);
      expect(find.text('Status: offered'), findsOneWidget);
    });

    testWidgets('renders empty state', (tester) async {
      final c = AssignmentListController(FakeDriverRepository(assignments: []));
      await tester.pumpWidget(listApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignments-empty')), findsOneWidget);
    });

    testWidgets('renders error state', (tester) async {
      final c = AssignmentListController(
        FakeDriverRepository(
          assignmentsError: const ApiError(status: 500, message: 'Server error'),
        ),
      );
      await tester.pumpWidget(listApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignments-error')), findsOneWidget);
      expect(find.byKey(const Key('assignments-retry')), findsOneWidget);
    });

    testWidgets('renders offline state with retry', (tester) async {
      final c = AssignmentListController(
        FakeDriverRepository(assignmentsError: ApiError.network()),
      );
      await tester.pumpWidget(listApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignments-offline')), findsOneWidget);
      expect(find.byKey(const Key('assignments-retry')), findsOneWidget);
    });

    testWidgets('shows no action/compliance buttons when loaded',
        (tester) async {
      final c = AssignmentListController(FakeDriverRepository());
      await tester.pumpWidget(listApp(c));
      await tester.pumpAndSettle();
      for (final label in _forbiddenActionLabels) {
        expect(find.widgetWithText(ElevatedButton, label), findsNothing);
        expect(find.widgetWithText(FilledButton, label), findsNothing);
        expect(find.widgetWithText(TextButton, label), findsNothing);
      }
    });
  });

  group('AssignmentDetailScreen', () {
    testWidgets('renders loading on the initial frame', (tester) async {
      final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
      await tester.pumpWidget(detailApp(c));
      expect(
        find.byKey(const Key('assignment-detail-loading')),
        findsOneWidget,
      );
      await tester.pumpAndSettle();
    });

    testWidgets('renders loaded detail + delivery state', (tester) async {
      final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
      await tester.pumpWidget(detailApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignment-detail-loaded')), findsOneWidget);
      expect(find.text('Status: started'), findsOneWidget);
      expect(find.text('State: en_route_to_store'), findsOneWidget);
    });

    testWidgets('renders error state with retry', (tester) async {
      final c = AssignmentDetailController(
        FakeDriverRepository(
          detailError: const ApiError(status: 404, message: 'Not found'),
        ),
        'a-1',
      );
      await tester.pumpWidget(detailApp(c));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('assignment-detail-error')), findsOneWidget);
      expect(find.byKey(const Key('assignment-detail-retry')), findsOneWidget);
    });

    testWidgets('renders offline state', (tester) async {
      final c = AssignmentDetailController(
        FakeDriverRepository(detailError: ApiError.network()),
        'a-1',
      );
      await tester.pumpWidget(detailApp(c));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('assignment-detail-offline')),
        findsOneWidget,
      );
    });

    testWidgets('shows no action/compliance buttons when loaded',
        (tester) async {
      final c = AssignmentDetailController(FakeDriverRepository(), 'a-1');
      await tester.pumpWidget(detailApp(c));
      await tester.pumpAndSettle();
      for (final label in _forbiddenActionLabels) {
        expect(find.widgetWithText(ElevatedButton, label), findsNothing);
        expect(find.widgetWithText(FilledButton, label), findsNothing);
        expect(find.widgetWithText(TextButton, label), findsNothing);
      }
    });
  });
}
