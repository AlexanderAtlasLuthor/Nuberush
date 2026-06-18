// Dr.1.3.F — assignment repository endpoint tests. MockClient only; no backend.

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

  test('fetchAssignments calls GET /driver/assignments', () async {
    final h = makeRepo((_) => json({
          'items': [
            {'id': 'a-1', 'order_id': 'o-1', 'store_id': 's-1', 'status': 'offered'},
          ],
          'total': 1,
          'limit': 50,
          'offset': 0,
        }));
    final list = await h.repo.fetchAssignments();
    expect(h.captured.single.method, 'GET');
    expect(h.captured.single.url.toString(),
        'https://api.example.com/driver/assignments');
    expect(list.single.id, 'a-1');
  });

  test('fetchAssignments default sends NO status query (Dr.1.5.K)', () async {
    final h = makeRepo((_) => json({'items': [], 'total': 0}));
    await h.repo.fetchAssignments();
    final url = h.captured.single.url;
    expect(url.toString(), 'https://api.example.com/driver/assignments');
    expect(url.queryParameters.containsKey('status'), isFalse);
  });

  test('fetchAssignments(status:) appends ?status=<terminal> (Dr.1.5.K)',
      () async {
    final h = makeRepo((_) => json({'items': [], 'total': 0}));
    await h.repo.fetchAssignments(status: 'completed');
    final url = h.captured.single.url;
    expect(url.path, '/driver/assignments');
    expect(url.queryParameters['status'], 'completed');
  });

  test('fetchAssignments(status: empty) sends no status query (Dr.1.5.K)',
      () async {
    final h = makeRepo((_) => json({'items': [], 'total': 0}));
    await h.repo.fetchAssignments(status: '');
    expect(h.captured.single.url.queryParameters.containsKey('status'), isFalse);
  });

  test('fetchAssignmentDetail calls GET /driver/assignments/{id}', () async {
    final h = makeRepo((_) => json({
          'id': 'a-9',
          'order_id': 'o-9',
          'store_id': 's-1',
          'status': 'started',
        }));
    final detail = await h.repo.fetchAssignmentDetail('a-9');
    expect(h.captured.single.url.toString(),
        'https://api.example.com/driver/assignments/a-9');
    expect(detail.id, 'a-9');
  });

  test('fetchDeliveryState calls GET /driver/assignments/{id}/delivery-state',
      () async {
    final h = makeRepo((_) => json({
          'id': 'ds-1',
          'assignment_id': 'a-9',
          'order_id': 'o-9',
          'state': 'picked_up',
        }));
    final ds = await h.repo.fetchDeliveryState('a-9');
    expect(h.captured.single.url.toString(),
        'https://api.example.com/driver/assignments/a-9/delivery-state');
    expect(ds.state, 'picked_up');
  });

  test('ApiError propagates from assignment detail', () async {
    final h = makeRepo(
      (_) => http.Response('{"detail": "Not found"}', 404,
          headers: {'content-type': 'application/json'}),
    );
    await expectLater(
      h.repo.fetchAssignmentDetail('missing'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 404)),
    );
  });

  test('network ApiError surfaces with status 0', () async {
    final h = makeRepo((_) => json({}), throwError: Exception('offline'));
    await expectLater(
      h.repo.fetchAssignments(),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 0)),
    );
  });
}
