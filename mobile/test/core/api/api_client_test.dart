// Dr.1.3.C — ApiClient transport tests. Pure Dart with a mocked http.Client
// (package:http/testing.dart MockClient). No real backend, no Supabase, no env.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/api/api_error.dart';

void main() {
  final config = ApiConfig.fromBaseUrl('https://api.example.com');

  /// Build a client whose mock captures the last request and replies via
  /// [respond]. If [throwError] is set, the transport throws (network failure).
  ({ApiClient client, List<http.Request> captured}) makeClient(
    http.Response Function(http.Request req) respond, {
    AccessTokenProvider? tokenProvider,
    Object? throwError,
  }) {
    final captured = <http.Request>[];
    final mock = MockClient((http.Request req) async {
      captured.add(req);
      if (throwError != null) throw throwError;
      return respond(req);
    });
    final client = ApiClient(
      config: config,
      httpClient: mock,
      accessTokenProvider: tokenProvider,
    );
    return (client: client, captured: captured);
  }

  http.Response json(Object body, {int status = 200}) => http.Response(
        jsonEncode(body),
        status,
        headers: {'content-type': 'application/json'},
      );

  group('headers', () {
    test('GET attaches Accept: application/json and no Content-Type', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.get('/driver/me');
      final req = h.captured.single;
      expect(req.method, 'GET');
      expect(req.headers['Accept'], 'application/json');
      // http sets a default content-type for an empty GET body; the client
      // must not have explicitly added a JSON content-type for a bodyless GET.
      expect(req.body, '');
    });

    test('JSON POST attaches Content-Type and JSON-encoded body', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.post('/driver/assignments/x/start', body: {'a': 1});
      final req = h.captured.single;
      expect(req.method, 'POST');
      expect(req.headers['Content-Type'], contains('application/json'));
      expect(jsonDecode(req.body), {'a': 1});
    });

    test('Bearer attaches when the token provider yields a token', () async {
      final h = makeClient(
        (_) => json({'ok': true}),
        tokenProvider: () async => 'tok-123',
      );
      await h.client.get('/driver/me');
      expect(h.captured.single.headers['Authorization'], 'Bearer tok-123');
    });

    test('Authorization omitted when token provider returns null', () async {
      final h = makeClient(
        (_) => json({'ok': true}),
        tokenProvider: () async => null,
      );
      await h.client.get('/driver/me');
      expect(h.captured.single.headers.containsKey('Authorization'), isFalse);
    });

    test('Authorization omitted when there is no token provider', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.get('/driver/me');
      expect(h.captured.single.headers.containsKey('Authorization'), isFalse);
    });

    test('Idempotency-Key attaches when supplied', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.post(
        '/driver/assignments/x/complete',
        body: {},
        idempotencyKey: 'key-abc',
      );
      expect(h.captured.single.headers['Idempotency-Key'], 'key-abc');
    });
  });

  group('success decoding', () {
    test('204 returns null', () async {
      final h = makeClient((_) => http.Response('', 204));
      expect(await h.client.post('/x'), isNull);
    });

    test('empty 200 body returns null', () async {
      final h = makeClient((_) => http.Response('', 200));
      expect(await h.client.get('/x'), isNull);
    });

    test('2xx JSON returns the decoded body', () async {
      final h = makeClient((_) => json({'id': 7, 'name': 'NubeRush'}));
      final result = await h.client.get('/driver/me');
      expect(result, {'id': 7, 'name': 'NubeRush'});
    });

    test('2xx JSON array decodes', () async {
      final h = makeClient((_) => json([1, 2, 3]));
      expect(await h.client.get('/driver/assignments'), [1, 2, 3]);
    });
  });

  group('error normalization', () {
    test('4xx FastAPI string detail throws normalized ApiError', () async {
      final h = makeClient(
        (_) => http.Response(
          '{"detail": "Not authenticated"}',
          401,
          headers: {'content-type': 'application/json'},
        ),
      );
      await expectLater(
        h.client.get('/driver/me'),
        throwsA(
          isA<ApiError>()
              .having((e) => e.status, 'status', 401)
              .having((e) => e.message, 'message', 'Not authenticated'),
        ),
      );
    });

    test('422 Pydantic detail array throws normalized ApiError', () async {
      final h = makeClient(
        (_) => http.Response(
          '{"detail": [{"msg": "Field required", "type": "missing"}]}',
          422,
          headers: {'content-type': 'application/json'},
        ),
      );
      await expectLater(
        h.client.post('/x', body: {}),
        throwsA(
          isA<ApiError>()
              .having((e) => e.status, 'status', 422)
              .having((e) => e.message, 'message', 'Field required'),
        ),
      );
    });

    test('500 empty body throws ApiError with fallback message', () async {
      final h = makeClient((_) => http.Response('', 500));
      await expectLater(
        h.client.get('/x'),
        throwsA(
          isA<ApiError>()
              .having((e) => e.status, 'status', 500)
              .having((e) => e.message, 'message', 'Request failed'),
        ),
      );
    });

    test('transport exception throws ApiError with status 0', () async {
      final h = makeClient(
        (_) => json({'ok': true}),
        throwError: Exception('socket down'),
      );
      await expectLater(
        h.client.get('/x'),
        throwsA(
          isA<ApiError>().having((e) => e.status, 'status', 0),
        ),
      );
    });
  });

  group('path + query building', () {
    test('leading-slash path joins without double slash', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.get('/driver/me');
      expect(h.captured.single.url.toString(),
          'https://api.example.com/driver/me');
    });

    test('slashless path joins correctly', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.get('driver/me');
      expect(h.captured.single.url.toString(),
          'https://api.example.com/driver/me');
    });

    test('base path + request path compose without double slash', () async {
      final cfg = ApiConfig.fromBaseUrl('https://api.example.com/api/');
      final captured = <http.Request>[];
      final mock = MockClient((req) async {
        captured.add(req);
        return json({'ok': true});
      });
      final client = ApiClient(config: cfg, httpClient: mock);
      await client.get('/driver/me');
      expect(captured.single.url.toString(),
          'https://api.example.com/api/driver/me');
    });

    test('query parameters are encoded; null values dropped', () async {
      final h = makeClient((_) => json({'ok': true}));
      await h.client.get('/driver/assignments',
          query: {'status': 'open', 'limit': 10, 'cursor': null});
      final url = h.captured.single.url;
      expect(url.path, '/driver/assignments');
      expect(url.queryParameters['status'], 'open');
      expect(url.queryParameters['limit'], '10');
      expect(url.queryParameters.containsKey('cursor'), isFalse);
    });
  });
}
