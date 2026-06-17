// Dr.1.3.E — DriverHomeScreen widget tests. Fake repo, no network/Supabase.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_screen.dart';

import 'fake_driver_repository.dart';

void main() {
  Widget appWith(DriverHomeController controller) =>
      NubeRushDriverApp(home: DriverHomeScreen(controller: controller));

  testWidgets('renders the NubeRush Driver title', (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller));
    expect(find.text('NubeRush Driver'), findsWidgets);
  });

  testWidgets('shows loading then loaded profile + eligibility',
      (tester) async {
    final controller = DriverHomeController(FakeDriverRepository());
    await tester.pumpWidget(appWith(controller));
    // The initial frame (before the post-frame load resolves) shows loading.
    expect(find.byKey(const Key('driver-home-loading')), findsOneWidget);

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('driver-home-loaded')), findsOneWidget);
    expect(find.text('Status: active'), findsOneWidget);
    expect(find.text('You can go online.'), findsOneWidget);
  });

  testWidgets('loaded with blockers shows cannot-go-online + reason',
      (tester) async {
    final controller = DriverHomeController(
      FakeDriverRepository(eligibility: sampleEligibility(canGoOnline: false)),
    );
    await tester.pumpWidget(appWith(controller));
    await tester.pumpAndSettle();
    expect(find.text('You cannot go online yet.'), findsOneWidget);
    expect(find.text('• Approval pending'), findsOneWidget);
  });

  testWidgets('error state renders safe error text with retry',
      (tester) async {
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
