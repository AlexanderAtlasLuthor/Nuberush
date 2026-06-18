// NubeRush Driver — LoginScreen widget tests (Dr.1.4.D).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/auth_controller.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';
import 'package:nuberush_driver/core/ui/ui.dart';
import 'package:nuberush_driver/features/auth/presentation/login_screen.dart';

import '../../core/auth/auth_controller_test.dart' show FakeAuthActions;

Widget _host(Widget child) =>
    MaterialApp(theme: NubeRushTheme.dark(), home: child);

void main() {
  testWidgets('renders NubeRush brand, title, fields and button',
      (tester) async {
    final controller = AuthController(FakeAuthActions());
    await tester.pumpWidget(_host(LoginScreen(controller: controller)));

    expect(find.byType(NubeRushBrandHeader), findsOneWidget);
    expect(find.text('Sign in to drive'), findsOneWidget);
    expect(find.byKey(const Key('login-email')), findsOneWidget);
    expect(find.byKey(const Key('login-password')), findsOneWidget);
    expect(find.byKey(const Key('login-submit')), findsOneWidget);
  });

  testWidgets('password field obscures text', (tester) async {
    final controller = AuthController(FakeAuthActions());
    await tester.pumpWidget(_host(LoginScreen(controller: controller)));

    final field = tester.widget<NubeRushTextField>(
      find.byKey(const Key('login-password')),
    );
    expect(field.obscureText, isTrue);
  });

  testWidgets('empty fields show a safe validation error and skip actions',
      (tester) async {
    final actions = FakeAuthActions();
    final controller = AuthController(actions);
    await tester.pumpWidget(_host(LoginScreen(controller: controller)));

    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pump();

    expect(find.byType(NubeRushInlineError), findsOneWidget);
    expect(actions.signInCount, 0);
  });

  testWidgets('successful submit calls onSignedIn', (tester) async {
    final controller = AuthController(FakeAuthActions());
    var signedIn = false;
    await tester.pumpWidget(_host(LoginScreen(
      controller: controller,
      onSignedIn: () => signedIn = true,
    )));

    await tester.enterText(
        find.byKey(const Key('login-email')), 'driver@nuberush.test');
    await tester.enterText(find.byKey(const Key('login-password')), 'pw');
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect(signedIn, isTrue);
  });

  testWidgets('failed submit renders a safe inline error, not a raw exception',
      (tester) async {
    final controller = AuthController(FakeAuthActions(failSignIn: true));
    await tester.pumpWidget(_host(LoginScreen(controller: controller)));

    await tester.enterText(
        find.byKey(const Key('login-email')), 'driver@nuberush.test');
    await tester.enterText(find.byKey(const Key('login-password')), 'pw');
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect(find.byType(NubeRushInlineError), findsOneWidget);
    expect(find.textContaining('Exception'), findsNothing);
    expect(find.textContaining('401'), findsNothing);
  });
}
