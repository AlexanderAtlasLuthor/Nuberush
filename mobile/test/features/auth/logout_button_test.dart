// NubeRush Driver — LogoutButton widget tests (Dr.1.4.D).

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/auth_controller.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';
import 'package:nuberush_driver/features/auth/presentation/logout_button.dart';

import '../../core/auth/auth_controller_test.dart' show FakeAuthActions;

/// AuthActions whose signOut stays pending until [complete] is called, so the
/// in-flight loading state can be observed deterministically.
class BlockingAuthActions implements AuthActions {
  final Completer<void> _signOut = Completer<void>();

  void complete() => _signOut.complete();

  @override
  Future<void> signInWithPassword({
    required String email,
    required String password,
  }) async {}

  @override
  Future<void> signOut() => _signOut.future;
}

Widget _host(Widget child) => MaterialApp(
      theme: NubeRushTheme.dark(),
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  testWidgets('renders the sign out label', (tester) async {
    final controller = AuthController(FakeAuthActions());
    await tester.pumpWidget(_host(LogoutButton(controller: controller)));
    expect(find.text('Sign out'), findsOneWidget);
  });

  testWidgets('invokes controller signOut and calls onSignedOut on success',
      (tester) async {
    final actions = FakeAuthActions();
    final controller = AuthController(actions);
    var signedOut = false;
    await tester.pumpWidget(_host(LogoutButton(
      controller: controller,
      onSignedOut: () => signedOut = true,
    )));

    await tester.tap(find.byKey(const Key('logout-button')));
    await tester.pumpAndSettle();

    expect(actions.signOutCount, 1);
    expect(signedOut, isTrue);
  });

  testWidgets('shows a loading state while sign-out is in flight',
      (tester) async {
    final actions = BlockingAuthActions();
    final controller = AuthController(actions);
    await tester.pumpWidget(_host(LogoutButton(controller: controller)));

    await tester.tap(find.byKey(const Key('logout-button')));
    await tester.pump(); // start the async signOut; busy = true, still pending

    expect(find.byKey(const Key('logout-button-loading')), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    actions.complete(); // let signOut resolve
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('logout-button')), findsOneWidget);
  });

  testWidgets('failed sign-out surfaces a safe message', (tester) async {
    final controller = AuthController(FakeAuthActions(failSignOut: true));
    var signedOut = false;
    await tester.pumpWidget(_host(LogoutButton(
      controller: controller,
      onSignedOut: () => signedOut = true,
    )));

    await tester.tap(find.byKey(const Key('logout-button')));
    await tester.pumpAndSettle();

    expect(signedOut, isFalse);
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.textContaining('Exception'), findsNothing);
  });
}
