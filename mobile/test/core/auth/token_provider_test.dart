// Dr.1.3.D — TokenProvider bridge tests. Confirms the AuthSession-derived
// provider feeds ApiClient's Bearer header. No real Supabase/backend.

import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/auth/auth_session.dart';
import 'package:nuberush_driver/core/auth/secure_session_store.dart';
import 'package:nuberush_driver/core/auth/token_provider.dart';

/// Minimal fake gateway with a settable token.
class FakeGateway implements SupabaseAuthGateway {
  FakeGateway(this._token);
  String? _token;
  @override
  String? get currentAccessToken => _token;
  @override
  Stream<String?> get onAccessTokenChanged => const Stream<String?>.empty();
  @override
  Future<void> signOut() async => _token = null;
}

void main() {
  final config = ApiConfig.fromBaseUrl('https://api.example.com');

  AuthSession sessionWith(String? token) => SupabaseAuthSession(
        gateway: FakeGateway(token),
        secureStore: InMemorySecureSessionStore(),
      );

  test('provider returns the token from the AuthSession', () async {
    final provider = accessTokenProviderFor(sessionWith('tok-1'));
    expect(await provider(), 'tok-1');
  });

  test('provider returns null when unauthenticated', () async {
    final provider = accessTokenProviderFor(sessionWith(null));
    expect(await provider(), isNull);
  });

  test('ApiClient attaches Bearer from the provider', () async {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      return http.Response(jsonEncode({'ok': true}), 200,
          headers: {'content-type': 'application/json'});
    });
    final client = ApiClient(
      config: config,
      httpClient: mock,
      accessTokenProvider: accessTokenProviderFor(sessionWith('tok-xyz')),
    );
    await client.get('/driver/me');
    expect(captured.single.headers['Authorization'], 'Bearer tok-xyz');
  });

  test('ApiClient omits Authorization when provider yields null', () async {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      return http.Response(jsonEncode({'ok': true}), 200,
          headers: {'content-type': 'application/json'});
    });
    final client = ApiClient(
      config: config,
      httpClient: mock,
      accessTokenProvider: accessTokenProviderFor(sessionWith(null)),
    );
    await client.get('/driver/me');
    expect(captured.single.headers.containsKey('Authorization'), isFalse);
  });
}
