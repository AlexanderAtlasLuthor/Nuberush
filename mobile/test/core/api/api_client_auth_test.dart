// NubeRush Driver — ApiClient token + 401/403 policy tests (Dr.1.4.F).

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/api/api_error.dart';

final _config = ApiConfig.fromBaseUrl('https://api.example.com');
const _jsonHeaders = {'content-type': 'application/json'};

void main() {
  test('attaches Authorization: Bearer when the provider returns a token',
      () async {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => 'live-token',
    );

    await client.get('/driver/me');
    expect(captured.single.headers['Authorization'], 'Bearer live-token');
  });

  test('omits Authorization when there is no token', () async {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => null,
    );

    await client.get('/driver/me');
    expect(captured.single.headers.containsKey('Authorization'), isFalse);
  });

  test('401 fires onUnauthorized once, throws 401, and does not retry',
      () async {
    var requests = 0;
    var unauthorizedCalls = 0;
    final mock = MockClient((req) async {
      requests++;
      return http.Response(
        jsonEncode({'detail': 'Not authenticated'}),
        401,
        headers: _jsonHeaders,
      );
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => 'tok',
      onUnauthorized: () async => unauthorizedCalls++,
    );

    await expectLater(
      client.get('/driver/me'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 401)),
    );
    expect(unauthorizedCalls, 1);
    expect(requests, 1, reason: 'no auto-retry on 401');
  });

  test('401 on a mutating POST fires handler once and is not auto-retried',
      () async {
    var requests = 0;
    var unauthorizedCalls = 0;
    final mock = MockClient((req) async {
      requests++;
      return http.Response('', 401);
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => 'tok',
      onUnauthorized: () async => unauthorizedCalls++,
    );

    await expectLater(
      client.post('/driver/assignments/a-1/accept'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 401)),
    );
    expect(unauthorizedCalls, 1);
    expect(requests, 1, reason: 'mutations are not auto-retried on 401');
  });

  test('403 does NOT fire onUnauthorized and surfaces a normalized 403',
      () async {
    var unauthorizedCalls = 0;
    final mock = MockClient((req) async {
      return http.Response(
        jsonEncode({'detail': 'Not allowed'}),
        403,
        headers: _jsonHeaders,
      );
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => 'tok',
      onUnauthorized: () async => unauthorizedCalls++,
    );

    await expectLater(
      client.get('/driver/me'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)),
    );
    expect(unauthorizedCalls, 0, reason: '403 must not sign the user out');
  });

  test('200 does not fire onUnauthorized', () async {
    var unauthorizedCalls = 0;
    final mock = MockClient((req) async {
      return http.Response(jsonEncode({'ok': true}), 200, headers: _jsonHeaders);
    });
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => 'tok',
      onUnauthorized: () async => unauthorizedCalls++,
    );

    await client.get('/driver/me');
    expect(unauthorizedCalls, 0);
  });
}
