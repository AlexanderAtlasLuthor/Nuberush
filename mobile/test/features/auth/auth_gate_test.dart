// NubeRush Driver — AuthGate / authenticated shell tests (Dr.1.4.E).
// Fakes stand in for Supabase; no real client, env, or network.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/auth_controller.dart';
import 'package:nuberush_driver/core/auth/auth_session.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';
import 'package:nuberush_driver/features/auth/presentation/auth_gate.dart';
import 'package:nuberush_driver/features/auth/presentation/auth_loading_screen.dart';
import 'package:nuberush_driver/features/auth/presentation/login_screen.dart';
import 'package:nuberush_driver/features/auth/presentation/logout_button.dart';

import '../../core/auth/auth_controller_test.dart' show FakeAuthActions;

/// Controllable [AuthSession] fake: settable initial token + a stream the test
/// drives to simulate login/logout. [gate] can delay the initial restore.
class FakeAuthSession implements AuthSession {
  FakeAuthSession({String? token}) : _token = token;

  String? _token;
  Completer<void>? gate;
  final StreamController<AuthSessionState> _controller =
      StreamController<AuthSessionState>.broadcast();

  void emit(AuthSessionState state) => _controller.add(state);
  set token(String? value) => _token = value;

  @override
  Future<String?> getAccessToken() async {
    if (gate != null) await gate!.future;
    return _token;
  }

  @override
  Stream<AuthSessionState> get authStateChanges => _controller.stream;

  @override
  Future<void> signOut() async => _token = null;
}

Widget _host(Widget child) =>
    MaterialApp(theme: NubeRushTheme.dark(), home: child);

AuthController _controller() => AuthController(FakeAuthActions());

void main() {
  testWidgets('launch with an existing session shows the authenticated shell',
      (tester) async {
    final session = FakeAuthSession(token: 'restored-token');
    await tester.pumpWidget(_host(
      AuthGate(session: session, controller: _controller()),
    ));
    await tester.pumpAndSettle();

    // Driver Home path is shown (its title), with a logout affordance, and no
    // login screen.
    expect(find.text('NubeRush Driver'), findsWidgets);
    expect(find.byType(LogoutButton), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('launch with no session shows the LoginScreen', (tester) async {
    final session = FakeAuthSession(token: null);
    await tester.pumpWidget(_host(
      AuthGate(session: session, controller: _controller()),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(LogoutButton), findsNothing);
  });

  testWidgets('shows a loading state while the session is being restored',
      (tester) async {
    final session = FakeAuthSession(token: 'tok')..gate = Completer<void>();
    await tester.pumpWidget(_host(
      AuthGate(session: session, controller: _controller()),
    ));
    await tester.pump(); // initial restore is gated → still resolving

    expect(find.byType(AuthLoadingScreen), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);

    session.gate!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(AuthLoadingScreen), findsNothing);
  });

  testWidgets('login then logout swaps the tree via the auth stream',
      (tester) async {
    final session = FakeAuthSession(token: null);
    await tester.pumpWidget(_host(
      AuthGate(session: session, controller: _controller()),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);

    // Simulate a successful sign-in (stream emits authenticated).
    session.emit(AuthSessionState.authenticated);
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsNothing);
    expect(find.byType(LogoutButton), findsOneWidget);

    // Simulate sign-out (stream emits unauthenticated).
    session.emit(AuthSessionState.unauthenticated);
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(LogoutButton), findsNothing);
  });
}
