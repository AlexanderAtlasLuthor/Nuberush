// Dr.1.3.H — compliance repository tests: exact POST paths, bodies, and
// Idempotency-Key. MockClient only; no backend.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/data/driver_repository.dart';
import 'package:nuberush_driver/features/driver/domain/compliance_requests.dart';

void main() {
  final config = ApiConfig.fromBaseUrl('https://api.example.com');
  const base = 'https://api.example.com/driver/assignments/a-1';

  ({ApiDriverRepository repo, List<http.Request> captured}) makeRepo({
    Object? throwError,
    List<String>? keys,
  }) {
    final captured = <http.Request>[];
    var i = 0;
    final mock = MockClient((req) async {
      captured.add(req);
      if (throwError != null) throw throwError;
      return http.Response(jsonEncode({'ok': true}), 200,
          headers: {'content-type': 'application/json'});
    });
    final repo = ApiDriverRepository(
      ApiClient(config: config, httpClient: mock),
      keyGenerator: keys == null ? null : () => keys[i++],
    );
    return (repo: repo, captured: captured);
  }

  test('verifyAge POSTs the body + Idempotency-Key', () async {
    final h = makeRepo(keys: ['k-1']);
    await h.repo.verifyAge(
      'a-1',
      const VerifyAgeRequest(outcome: VerifyAgeOutcome.pass),
    );
    final req = h.captured.single;
    expect(req.method, 'POST');
    expect(req.url.toString(), '$base/verify-age');
    expect(jsonDecode(req.body), {'outcome': 'pass'});
    expect(req.headers['Idempotency-Key'], 'k-1');
  });

  test('submitProof POSTs the three confirmations + key', () async {
    final h = makeRepo(keys: ['k-2']);
    await h.repo.submitProof(
      'a-1',
      const ProofRequest(
        recipientPresentConfirmed: true,
        handoffConfirmed: true,
        restrictedNotLeftUnattended: true,
      ),
    );
    final req = h.captured.single;
    expect(req.url.toString(), '$base/proof');
    expect(jsonDecode(req.body)['handoff_confirmed'], true);
    expect(req.headers['Idempotency-Key'], 'k-2');
  });

  test('completeDelivery is bodyless but carries a key', () async {
    final h = makeRepo(keys: ['k-3']);
    await h.repo.completeDelivery('a-1');
    final req = h.captured.single;
    expect(req.url.toString(), '$base/complete');
    expect(req.body, isEmpty);
    expect(req.headers['Idempotency-Key'], 'k-3');
  });

  test('failDelivery POSTs reason_code + key', () async {
    final h = makeRepo(keys: ['k-4']);
    await h.repo.failDelivery(
      'a-1',
      const FailRequest(reasonCode: FailureReason.customerUnavailable),
    );
    final req = h.captured.single;
    expect(req.url.toString(), '$base/fail');
    expect(jsonDecode(req.body)['reason_code'], 'customer_unavailable');
    expect(req.headers['Idempotency-Key'], 'k-4');
  });

  test('returnToStore POSTs action + key', () async {
    final h = makeRepo(keys: ['k-5']);
    await h.repo.returnToStore(
      'a-1',
      const ReturnToStoreRequest(action: ReturnAction.start),
    );
    final req = h.captured.single;
    expect(req.url.toString(), '$base/return-to-store');
    expect(jsonDecode(req.body)['action'], 'start');
    expect(req.headers['Idempotency-Key'], 'k-5');
  });

  test('separate attempts get distinct keys', () async {
    final h = makeRepo(keys: ['k-a', 'k-b']);
    await h.repo.completeDelivery('a-1');
    await h.repo.completeDelivery('a-1');
    expect(h.captured[0].headers['Idempotency-Key'], 'k-a');
    expect(h.captured[1].headers['Idempotency-Key'], 'k-b');
  });

  test('default generator produces non-empty unique keys', () async {
    final h = makeRepo(); // default generator
    await h.repo.completeDelivery('a-1');
    await h.repo.completeDelivery('a-1');
    final k1 = h.captured[0].headers['Idempotency-Key'];
    final k2 = h.captured[1].headers['Idempotency-Key'];
    expect(k1, isNotEmpty);
    expect(k2, isNotEmpty);
    expect(k1, isNot(k2));
  });

  test('ApiError propagates (e.g. 422 gate failure)', () async {
    final mock = MockClient((_) async => http.Response(
          '{"detail": [{"msg": "proof required", "type": "missing"}]}',
          422,
          headers: {'content-type': 'application/json'},
        ));
    final repo = ApiDriverRepository(ApiClient(config: config, httpClient: mock));
    await expectLater(
      repo.completeDelivery('a-1'),
      throwsA(isA<ApiError>()
          .having((e) => e.status, 'status', 422)
          .having((e) => e.message, 'message', 'proof required')),
    );
  });
}
