// Dr.1.3.G — operational action repository tests. MockClient only; no backend.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/data/driver_repository.dart';

void main() {
  final config = ApiConfig.fromBaseUrl('https://api.example.com');

  ({ApiDriverRepository repo, List<http.Request> captured}) makeRepo({
    Object? throwError,
  }) {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      if (throwError != null) throw throwError;
      return http.Response(jsonEncode({'ok': true}), 200,
          headers: {'content-type': 'application/json'});
    });
    return (
      repo: ApiDriverRepository(ApiClient(config: config, httpClient: mock)),
      captured: captured,
    );
  }

  const base = 'https://api.example.com/driver/assignments/a-1';

  final cases = <String, Future<void> Function(ApiDriverRepository)>{
    '$base/accept': (r) => r.acceptAssignment('a-1'),
    '$base/decline': (r) => r.declineAssignment('a-1'),
    '$base/start': (r) => r.startAssignment('a-1'),
    '$base/arrive-store': (r) => r.arriveStore('a-1'),
    '$base/pickup': (r) => r.pickupAssignment('a-1'),
    '$base/depart-to-customer': (r) => r.departToCustomer('a-1'),
    '$base/arrive-customer': (r) => r.arriveCustomer('a-1'),
  };

  cases.forEach((expectedUrl, invoke) {
    test('POST to $expectedUrl (bodyless)', () async {
      final h = makeRepo();
      await invoke(h.repo);
      final req = h.captured.single;
      expect(req.method, 'POST');
      expect(req.url.toString(), expectedUrl);
      expect(req.body, isEmpty); // bodyless — no invented payload
    });
  });

  test('ApiError propagates from an action (e.g. 409 conflict)', () async {
    final h = makeRepo(throwError: null);
    final conflictMock = MockClient((_) async => http.Response(
          '{"detail": "Already accepted"}',
          409,
          headers: {'content-type': 'application/json'},
        ));
    final repo = ApiDriverRepository(
      ApiClient(config: config, httpClient: conflictMock),
    );
    await expectLater(
      repo.declineAssignment('a-1'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 409)),
    );
    // Reference h to avoid unused warning.
    expect(h.captured, isEmpty);
  });

  test('network failure surfaces ApiError status 0', () async {
    final h = makeRepo(throwError: Exception('offline'));
    await expectLater(
      h.repo.acceptAssignment('a-1'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 0)),
    );
  });
}
