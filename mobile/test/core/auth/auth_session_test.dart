// Dr.1.3.D — AuthSession tests. A fake gateway stands in for Supabase; no real
// Supabase client, no env vars, no network.

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/auth_session.dart';
import 'package:nuberush_driver/core/auth/secure_session_store.dart';

/// Controllable fake [SupabaseAuthGateway].
class FakeAuthGateway implements SupabaseAuthGateway {
  FakeAuthGateway({String? token}) : _token = token;

  String? _token;
  int signOutCount = 0;
  final StreamController<String?> _controller =
      StreamController<String?>.broadcast();

  /// Simulate a session change (login/logout/refresh).
  void emit(String? token) {
    _token = token;
    _controller.add(token);
  }

  @override
  String? get currentAccessToken => _token;

  @override
  Stream<String?> get onAccessTokenChanged => _controller.stream;

  @override
  Future<void> signOut() async {
    signOutCount++;
    _token = null;
  }
}

void main() {
  late FakeAuthGateway gateway;
  late InMemorySecureSessionStore store;
  late SupabaseAuthSession session;

  setUp(() {
    gateway = FakeAuthGateway();
    store = InMemorySecureSessionStore();
    session = SupabaseAuthSession(gateway: gateway, secureStore: store);
  });

  test('authenticated session returns the access token', () async {
    gateway.emit('tok-1');
    expect(await session.getAccessToken(), 'tok-1');
  });

  test('unauthenticated session returns null', () async {
    expect(await session.getAccessToken(), isNull);
  });

  test('empty token is treated as unauthenticated', () async {
    gateway.emit('');
    expect(await session.getAccessToken(), isNull);
  });

  test('token read is live/fresh, not stale-cached', () async {
    gateway.emit('tok-1');
    expect(await session.getAccessToken(), 'tok-1');
    // Token refreshes underneath; next read must reflect the new value.
    gateway.emit('tok-2');
    expect(await session.getAccessToken(), 'tok-2');
  });

  test('signOut calls the Supabase signOut boundary', () async {
    gateway.emit('tok-1');
    await session.signOut();
    expect(gateway.signOutCount, 1);
    expect(await session.getAccessToken(), isNull);
  });

  test('signOut clears the secure session store', () async {
    await store.writeAccessToken('a');
    await store.writeRefreshToken('r');
    await session.signOut();
    expect(await store.readAccessToken(), isNull);
    expect(await store.readRefreshToken(), isNull);
  });

  test('authStateChanges maps tokens to authenticated/unauthenticated',
      () async {
    final List<AuthSessionState> seen = <AuthSessionState>[];
    final sub = session.authStateChanges.listen(seen.add);
    gateway.emit('tok-1');
    gateway.emit(null);
    gateway.emit('tok-2');
    await Future<void>.delayed(Duration.zero);
    await sub.cancel();
    expect(seen, <AuthSessionState>[
      AuthSessionState.authenticated,
      AuthSessionState.unauthenticated,
      AuthSessionState.authenticated,
    ]);
  });
}
