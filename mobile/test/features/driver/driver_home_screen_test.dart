// Dr.1.5.C — Operations Home widget tests. Fake repo, no network/Supabase.
//
// Covers the Dr.1.3.E states that must be preserved (loading / loaded /
// error / offline / unauthenticated / retry) plus the new Dr.1.5.C surface:
// readiness, presentation-only online toggle (no backend call), operational
// entry points, and honest "coming soon" placeholders.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_screen.dart';

import 'fake_driver_repository.dart';

void main() {
  Widget appWith(
    DriverHomeController controller, {
    void Function(BuildContext)? onViewAssignments,
    void Function(BuildContext)? onViewOffers,
    void Function(BuildContext)? onViewHistory,
  }) =>
      NubeRushDriverApp(
        home: DriverHomeScreen(
          controller: controller,
          onViewAssignments: onViewAssignments,
          onViewOffers: onViewOffers,
          onViewHistory: onViewHistory,
        ),
      );

  testWidgets('renders the NubeRush Driver title', (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller));
    expect(find.text('NubeRush Driver'), findsWidgets);
  });

  testWidgets('shows loading then loaded operations home', (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller));
    // The initial frame (before the post-frame load resolves) shows loading.
    expect(find.byKey(const Key('driver-home-loading')), findsOneWidget);

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-loaded')), findsOneWidget);
    expect(find.byKey(const Key('driver-home-status-card')), findsOneWidget);
    expect(find.text('active'), findsOneWidget);
    expect(find.text('You can go online.'), findsOneWidget);
    expect(find.text('Ready to go online'), findsOneWidget);
  });

  testWidgets('eligible driver sees the online toggle (presentation-only)',
      (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('driver-home-online-toggle')), findsOneWidget);
    expect(find.text('Presentation mode: offline'), findsOneWidget);
    // The honest dispatch disclaimer is always shown.
    expect(
      find.byKey(const Key('driver-home-online-disclaimer')),
      findsOneWidget,
    );
    expect(find.text(kOnlineDispatchDisclaimer), findsOneWidget);
  });

  testWidgets('toggling online updates presentation copy without a backend call',
      (tester) async {
    final repo = FakeDriverRepository();
    final controller = DriverHomeController(repo);
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();

    // Snapshot every repository counter after the initial load.
    final profileCalls = repo.profileCalls;
    final eligibilityCalls = repo.eligibilityCalls;
    final assignmentsCalls = repo.assignmentsCalls;
    final actionCalls = Map<String, int>.from(repo.actionCalls);

    final toggle = find.byKey(const Key('driver-home-online-toggle'));
    await tester.ensureVisible(toggle);
    await tester.pumpAndSettle();
    await tester.tap(toggle);
    await tester.pumpAndSettle();

    expect(find.text('Presentation mode: online'), findsOneWidget);
    expect(find.text('You look ready to drive.'), findsOneWidget);

    // No repository/API call of any kind was triggered by the local toggle.
    expect(repo.profileCalls, profileCalls);
    expect(repo.eligibilityCalls, eligibilityCalls);
    expect(repo.assignmentsCalls, assignmentsCalls);
    expect(repo.actionCalls, actionCalls);
    // The home never fetches assignments or runs actions on its own.
    expect(repo.assignmentsCalls, 0);
    expect(repo.actionCalls, isEmpty);
  });

  testWidgets('ineligible driver sees blocked state, blockers, and no toggle',
      (tester) async {
    final controller = DriverHomeController(
      FakeDriverRepository(eligibility: sampleEligibility(canGoOnline: false)),
    );
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();

    expect(find.text('You cannot go online yet.'), findsOneWidget);
    expect(find.text('Not ready yet'), findsOneWidget);
    expect(find.byKey(const Key('driver-home-blockers-card')), findsOneWidget);
    expect(find.text('• Approval pending'), findsOneWidget);
    // An ineligible driver must never be offered the online toggle.
    expect(find.byKey(const Key('driver-home-online-toggle')), findsNothing);
  });

  testWidgets('assignments / offers / active entry points navigate via the '
      'existing assignment-list callback', (tester) async {
    final repo = FakeDriverRepository();
    final controller = DriverHomeController(repo);
    var navCount = 0;
    await tester.pumpWidget(
      appWith(controller, onViewAssignments: (_) => navCount++),
    );
    await tester.pumpAndSettle();

    Future<void> tapEntry(String key) async {
      final finder = find.byKey(Key(key));
      await tester.ensureVisible(finder);
      await tester.pumpAndSettle();
      await tester.tap(finder);
      await tester.pump();
    }

    await tapEntry('driver-home-ops-assignments');
    expect(navCount, 1);

    await tapEntry('driver-home-ops-offers');
    expect(navCount, 2);

    await tapEntry('driver-home-ops-active');
    expect(navCount, 3);

    // None of these entry points fetch assignments from the home itself.
    expect(repo.assignmentsCalls, 0);
    expect(repo.actionCalls, isEmpty);
  });

  testWidgets('offers entry opens the dedicated offer surface when wired',
      (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    var assignmentsNav = 0;
    var offersNav = 0;
    await tester.pumpWidget(appWith(
      controller,
      onViewAssignments: (_) => assignmentsNav++,
      onViewOffers: (_) => offersNav++,
    ));
    await tester.pumpAndSettle();

    final offers = find.byKey(const Key('driver-home-ops-offers'));
    await tester.ensureVisible(offers);
    await tester.pumpAndSettle();
    await tester.tap(offers);
    await tester.pump();

    // Offers routes to its dedicated surface, not the assignment list.
    expect(offersNav, 1);
    expect(assignmentsNav, 0);
  });

  testWidgets('safety & support opens the static safety toolkit (Dr.1.5.J)',
      (tester) async {
    final repo = FakeDriverRepository();
    final controller = DriverHomeController(repo);
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('driver-home-ops-safety'));
    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pumpAndSettle();

    // Opens the real local surface (not a coming-soon snackbar) and needs no
    // backend data to do so.
    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);
    expect(repo.assignmentsCalls, 0);
    expect(repo.actionCalls, isEmpty);
  });

  testWidgets('history entry opens the history surface when wired (Dr.1.5.K)',
      (tester) async {
    final repo = FakeDriverRepository();
    final controller = DriverHomeController(repo);
    var historyNav = 0;
    var assignmentsNav = 0;
    await tester.pumpWidget(appWith(
      controller,
      onViewAssignments: (_) => assignmentsNav++,
      onViewHistory: (_) => historyNav++,
    ));
    await tester.pumpAndSettle();

    final entry = find.byKey(const Key('driver-home-ops-history'));
    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry);
    await tester.pump();

    // Opens history (no coming-soon snackbar) and makes no backend call here.
    expect(historyNav, 1);
    expect(assignmentsNav, 0);
    expect(find.text('History is coming in a later update.'), findsNothing);
    expect(repo.assignmentsCalls, 0);
    expect(repo.actionCalls, isEmpty);
  });

  testWidgets('entry points that depend on navigation render disabled when no '
      'callback is wired', (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller)); // no onViewAssignments
    await tester.pumpAndSettle();

    // Tapping a disabled entry must be a no-op (no crash, no navigation).
    final entry = find.byKey(const Key('driver-home-ops-assignments'));
    await tester.ensureVisible(entry);
    await tester.pumpAndSettle();
    await tester.tap(entry, warnIfMissed: false);
    await tester.pump();
    expect(find.byKey(const Key('driver-home-loaded')), findsOneWidget);
  });

  testWidgets('error state renders safe error text with retry', (tester) async {
    final controller = DriverHomeController(
      FakeDriverRepository(
        profileError: const ApiError(status: 500, message: 'Server error'),
      ),
    );
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-error')), findsOneWidget);
    expect(find.text('Server error'), findsOneWidget);
    expect(find.byKey(const Key('driver-home-retry')), findsOneWidget);
  });

  testWidgets('offline state renders retry affordance', (tester) async {
    final controller = DriverHomeController(
      FakeDriverRepository(profileError: ApiError.network()),
    );
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-offline')), findsOneWidget);
    expect(find.byKey(const Key('driver-home-retry')), findsOneWidget);
  });

  testWidgets('unauthenticated state renders a safe message', (tester) async {
    final controller = DriverHomeController(
      FakeDriverRepository(
        profileError: const ApiError(status: 401, message: 'Not authenticated'),
      ),
    );
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-unauthenticated')), findsOneWidget);
  });

  testWidgets('retry recovers from offline to loaded', (tester) async {
    final repo = FakeDriverRepository(profileError: ApiError.network());
    final controller = DriverHomeController(repo);
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-offline')), findsOneWidget);

    repo.profileError = null;
    await tester.tap(find.byKey(const Key('driver-home-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-loaded')), findsOneWidget);
  });
}
