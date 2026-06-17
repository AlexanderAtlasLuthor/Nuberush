// Dr.1.3.E — read-only driver repository tests. MockClient only; no backend.

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

  ({ApiDriverRepository repo, List<http.Request> captured}) makeRepo(
    http.Response Function(http.Request req) respond, {
    Object? throwError,
  }) {
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      if (throwError != null) throw throwError;
      return respond(req);
    });
    return (
      repo: ApiDriverRepository(ApiClient(config: config, httpClient: mock)),
      captured: captured,
    );
  }

  http.Response json(Object body) => http.Response(
        jsonEncode(body),
        200,
        headers: {'content-type': 'application/json'},
      );

  test('fetchDriverProfile calls GET /driver/me', () async {
    final h = makeRepo((_) => json({
          'id': 'd-1',
          'user_id': 'u-1',
          'store_id': 's-1',
          'status': 'active',
          'approval_status': 'approved',
        }));
    final profile = await h.repo.fetchDriverProfile();
    expect(h.captured.single.method, 'GET');
    expect(h.captured.single.url.toString(),
        'https://api.example.com/driver/me');
    expect(profile.id, 'd-1');
  });

  test('fetchDriverEligibility calls GET /driver/eligibility', () async {
    final h = makeRepo((_) => json({
          'can_go_online': true,
          'blockers': [],
          'user_active': true,
          'evaluated_at': '2026-06-17T12:00:00Z',
        }));
    final eligibility = await h.repo.fetchDriverEligibility();
    expect(h.captured.single.url.toString(),
        'https://api.example.com/driver/eligibility');
    expect(eligibility.canGoOnline, isTrue);
  });

  test('ApiError from profile propagates', () async {
    final h = makeRepo(
      (_) => http.Response('{"detail": "Forbidden"}', 403,
          headers: {'content-type': 'application/json'}),
    );
    await expectLater(
      h.repo.fetchDriverProfile(),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)),
    );
  });

  test('network ApiError surfaces with status 0', () async {
    final h = makeRepo((_) => json({}), throwError: Exception('offline'));
    await expectLater(
      h.repo.fetchDriverEligibility(),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 0)),
    );
  });
}
