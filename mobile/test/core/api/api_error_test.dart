// Dr.1.3.C — ApiError normalization tests. Pure Dart, no network.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';

void main() {
  group('ApiError.fromResponse', () {
    test('FastAPI HTTPException string detail -> message', () {
      final err = ApiError.fromResponse(
        status: 401,
        body: '{"detail": "Not authenticated"}',
      );
      expect(err.status, 401);
      expect(err.message, 'Not authenticated');
      expect(err.details, isA<Map<String, dynamic>>());
    });

    test('FastAPI Pydantic detail array -> first msg', () {
      final err = ApiError.fromResponse(
        status: 422,
        body:
            '{"detail": [{"loc": ["body", "x"], "msg": "Field required", "type": "missing"}]}',
      );
      expect(err.status, 422);
      expect(err.message, 'Field required');
    });

    test('generic JSON message field -> message', () {
      final err = ApiError.fromResponse(
        status: 400,
        body: '{"message": "Bad thing", "code": "bad_thing"}',
      );
      expect(err.message, 'Bad thing');
      expect(err.code, 'bad_thing');
    });

    test('JSON object without a usable message -> fallback', () {
      final err = ApiError.fromResponse(
        status: 400,
        body: '{"foo": "bar"}',
      );
      expect(err.message, 'Request failed');
      expect(err.details, isA<Map<String, dynamic>>());
    });

    test('plain-text body -> message is the text', () {
      final err = ApiError.fromResponse(
        status: 502,
        body: 'Bad Gateway',
      );
      expect(err.status, 502);
      expect(err.message, 'Bad Gateway');
    });

    test('empty body -> fallback message', () {
      final err = ApiError.fromResponse(status: 500, body: '');
      expect(err.status, 500);
      expect(err.message, 'Request failed');
    });

    test('whitespace-only body -> fallback message', () {
      final err = ApiError.fromResponse(status: 500, body: '   \n ');
      expect(err.message, 'Request failed');
    });

    test('valid JSON that is not an object -> fallback with details', () {
      final err = ApiError.fromResponse(status: 400, body: '[1, 2, 3]');
      expect(err.message, 'Request failed');
      expect(err.details, isA<List<dynamic>>());
    });

    test('long plain-text body is bounded', () {
      final err = ApiError.fromResponse(status: 500, body: 'x' * 5000);
      expect(err.message.length, lessThanOrEqualTo(201));
      expect(err.message.endsWith('…'), isTrue);
    });
  });

  group('ApiError.network', () {
    test('has status 0 and a default message', () {
      final err = ApiError.network();
      expect(err.status, 0);
      expect(err.message, 'Network request failed');
    });

    test('accepts a custom message', () {
      final err = ApiError.network('Offline');
      expect(err.status, 0);
      expect(err.message, 'Offline');
    });
  });

  group('ApiError fields/equality', () {
    test('exposes status/message/details/code', () {
      const err = ApiError(
        status: 409,
        message: 'Conflict',
        details: {'k': 'v'},
        code: 'conflict',
      );
      expect(err.status, 409);
      expect(err.message, 'Conflict');
      expect(err.details, {'k': 'v'});
      expect(err.code, 'conflict');
    });

    test('equality compares status/message/code', () {
      const a = ApiError(status: 400, message: 'x', code: 'c');
      const b = ApiError(status: 400, message: 'x', code: 'c');
      const c = ApiError(status: 400, message: 'y', code: 'c');
      expect(a, equals(b));
      expect(a, isNot(equals(c)));
    });
  });
}
