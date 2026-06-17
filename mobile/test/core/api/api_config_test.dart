// Dr.1.3.C — ApiConfig unit tests. Pure Dart, no env vars, no network.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_config.dart';

void main() {
  group('ApiConfig.fromBaseUrl', () {
    test('accepts a valid https URL', () {
      final config = ApiConfig.fromBaseUrl('https://api.example.com');
      expect(config.baseUri.scheme, 'https');
      expect(config.baseUri.host, 'api.example.com');
      expect(config.baseUri.path, '');
    });

    test('accepts http and a port and a base path', () {
      final config = ApiConfig.fromBaseUrl('http://localhost:8000/api');
      expect(config.baseUri.scheme, 'http');
      expect(config.baseUri.host, 'localhost');
      expect(config.baseUri.port, 8000);
      expect(config.baseUri.path, '/api');
    });

    test('trims a single trailing slash', () {
      final config = ApiConfig.fromBaseUrl('https://api.example.com/');
      expect(config.baseUri.path, '');
      expect(config.baseUri.toString(), 'https://api.example.com');
    });

    test('trims multiple trailing slashes on a path', () {
      final config = ApiConfig.fromBaseUrl('https://api.example.com/v1///');
      expect(config.baseUri.path, '/v1');
    });

    test('drops a base-level query/fragment without leaving a dangling marker',
        () {
      final config =
          ApiConfig.fromBaseUrl('https://api.example.com/v1?x=1#frag');
      expect(config.baseUri.hasQuery, isFalse);
      expect(config.baseUri.hasFragment, isFalse);
      expect(config.baseUri.toString(), 'https://api.example.com/v1');
    });

    test('rejects an empty value', () {
      expect(() => ApiConfig.fromBaseUrl(''), throwsA(isA<ApiConfigError>()));
      expect(
        () => ApiConfig.fromBaseUrl('   '),
        throwsA(isA<ApiConfigError>()),
      );
    });

    test('rejects a relative / schemeless value', () {
      expect(
        () => ApiConfig.fromBaseUrl('api.example.com'),
        throwsA(isA<ApiConfigError>()),
      );
      expect(
        () => ApiConfig.fromBaseUrl('/driver/me'),
        throwsA(isA<ApiConfigError>()),
      );
    });

    test('rejects a non-http(s) scheme', () {
      expect(
        () => ApiConfig.fromBaseUrl('ftp://example.com'),
        throwsA(isA<ApiConfigError>()),
      );
    });
  });
}
