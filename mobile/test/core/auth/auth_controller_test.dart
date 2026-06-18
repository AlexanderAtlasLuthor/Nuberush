// NubeRush Driver — AuthController tests (Dr.1.4.D).
// A fake AuthActions stands in for Supabase; no real client, env, or network.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/auth_controller.dart';
import 'package:nuberush_driver/core/auth/auth_state.dart';

class FakeAuthActions implements AuthActions {
  FakeAuthActions({this.failSignIn = false, this.failSignOut = false});

  bool failSignIn;
  bool failSignOut;
  int signInCount = 0;
  int signOutCount = 0;
  String? lastEmail;
  String? lastPassword;

  @override
  Future<void> signInWithPassword({
    required String email,
    required String password,
  }) async {
    signInCount++;
    lastEmail = email;
    lastPassword = password;
    if (failSignIn) throw Exception('raw supabase error: bad creds 401');
  }

  @override
  Future<void> signOut() async {
    signOutCount++;
    if (failSignOut) throw Exception('raw supabase error on signout');
  }
}

void main() {
  group('AuthController', () {
    test('initial state is unauthenticated', () {
      final controller = AuthController(FakeAuthActions());
      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(controller.state.errorMessage, isNull);
    });

    test('successful sign-in transitions submitting -> authenticated', () async {
      final actions = FakeAuthActions();
      final controller = AuthController(actions);
      final seen = <AuthStatus>[];
      controller.addListener(() => seen.add(controller.state.status));

      final ok = await controller.signInWithPassword(
        email: 'driver@nuberush.test',
        password: 'pw',
      );

      expect(ok, isTrue);
      expect(seen, [AuthStatus.submitting, AuthStatus.authenticated]);
      expect(actions.signInCount, 1);
    });

    test('empty fields fail locally without calling actions', () async {
      final actions = FakeAuthActions();
      final controller = AuthController(actions);

      final ok = await controller.signInWithPassword(email: '', password: '');

      expect(ok, isFalse);
      expect(controller.state.status, AuthStatus.failure);
      expect(actions.signInCount, 0);
    });

    test('email is trimmed/normalized before sign-in', () async {
      final actions = FakeAuthActions();
      final controller = AuthController(actions);

      await controller.signInWithPassword(
        email: '  driver@nuberush.test  ',
        password: 'pw',
      );

      expect(actions.lastEmail, 'driver@nuberush.test');
    });

    test('failed sign-in transitions to failure with safe message', () async {
      final actions = FakeAuthActions(failSignIn: true);
      final controller = AuthController(actions);

      final ok = await controller.signInWithPassword(
        email: 'driver@nuberush.test',
        password: 'pw',
      );

      expect(ok, isFalse);
      expect(controller.state.status, AuthStatus.failure);
      final message = controller.state.errorMessage!;
      // Safe copy only — no raw exception text / status code leaked.
      expect(message, isNot(contains('Exception')));
      expect(message, isNot(contains('401')));
      expect(message, isNot(contains('raw supabase')));
    });

    test('password is never stored on the controller state', () async {
      final actions = FakeAuthActions(failSignIn: true);
      final controller = AuthController(actions);

      await controller.signInWithPassword(
        email: 'driver@nuberush.test',
        password: 'super-secret-pw',
      );

      expect(controller.state.toString(), isNot(contains('super-secret-pw')));
      expect(controller.state.errorMessage, isNot(contains('super-secret-pw')));
    });

    test('successful sign-out transitions to unauthenticated', () async {
      final actions = FakeAuthActions();
      final controller = AuthController(actions);

      final ok = await controller.signOut();

      expect(ok, isTrue);
      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(actions.signOutCount, 1);
    });

    test('failed sign-out shows a safe message', () async {
      final actions = FakeAuthActions(failSignOut: true);
      final controller = AuthController(actions);

      final ok = await controller.signOut();

      expect(ok, isFalse);
      expect(controller.state.status, AuthStatus.failure);
      expect(controller.state.errorMessage, isNot(contains('Exception')));
    });
  });
}
