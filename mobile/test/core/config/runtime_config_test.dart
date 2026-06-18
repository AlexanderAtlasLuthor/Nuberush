// NubeRush Driver — RuntimeConfig validation tests (Dr.1.4.C).

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/config/runtime_config.dart';

const _validApi = 'https://api.nuberush.test';
const _validSupabaseUrl = 'https://project.supabase.test';
const _validAnonKey = 'public-anon-key-value';

void main() {
  group('RuntimeConfig.fromValues', () {
    test('builds a RuntimeConfig from valid values', () {
      final config = RuntimeConfig.fromValues(
        apiBaseUrl: _validApi,
        supabaseUrl: _validSupabaseUrl,
        supabaseAnonKey: _validAnonKey,
      );
      expect(config.apiConfig.baseUri.host, 'api.nuberush.test');
      expect(config.supabaseConfig.url.host, 'project.supabase.test');
      expect(config.supabaseConfig.anonKey, _validAnonKey);
    });

    test('missing API base URL fails safely', () {
      expect(
        () => RuntimeConfig.fromValues(
          apiBaseUrl: '',
          supabaseUrl: _validSupabaseUrl,
          supabaseAnonKey: _validAnonKey,
        ),
        throwsA(isA<RuntimeConfigError>().having(
          (e) => e.invalidVariables,
          'invalidVariables',
          contains('NUBERUSH_API_BASE_URL'),
        )),
      );
    });

    test('missing Supabase URL fails safely', () {
      expect(
        () => RuntimeConfig.fromValues(
          apiBaseUrl: _validApi,
          supabaseUrl: '',
          supabaseAnonKey: _validAnonKey,
        ),
        throwsA(isA<RuntimeConfigError>().having(
          (e) => e.invalidVariables,
          'invalidVariables',
          contains('NUBERUSH_SUPABASE_URL'),
        )),
      );
    });

    test('missing Supabase anon key fails safely', () {
      expect(
        () => RuntimeConfig.fromValues(
          apiBaseUrl: _validApi,
          supabaseUrl: _validSupabaseUrl,
          supabaseAnonKey: '',
        ),
        throwsA(isA<RuntimeConfigError>().having(
          (e) => e.invalidVariables,
          'invalidVariables',
          contains('NUBERUSH_SUPABASE_ANON_KEY'),
        )),
      );
    });

    test('invalid API URL fails safely', () {
      expect(
        () => RuntimeConfig.fromValues(
          apiBaseUrl: 'not-a-url',
          supabaseUrl: _validSupabaseUrl,
          supabaseAnonKey: _validAnonKey,
        ),
        throwsA(isA<RuntimeConfigError>().having(
          (e) => e.invalidVariables,
          'invalidVariables',
          contains('NUBERUSH_API_BASE_URL'),
        )),
      );
    });

    test('invalid Supabase URL fails safely', () {
      expect(
        () => RuntimeConfig.fromValues(
          apiBaseUrl: _validApi,
          supabaseUrl: 'ftp://bad',
          supabaseAnonKey: _validAnonKey,
        ),
        throwsA(isA<RuntimeConfigError>().having(
          (e) => e.invalidVariables,
          'invalidVariables',
          contains('NUBERUSH_SUPABASE_URL'),
        )),
      );
    });

    test('error names variables but never leaks the offending value', () {
      const secretishValue = 'super-secret-anon-or-url-value';
      try {
        RuntimeConfig.fromValues(
          apiBaseUrl: secretishValue, // invalid (no scheme/authority)
          supabaseUrl: _validSupabaseUrl,
          supabaseAnonKey: _validAnonKey,
        );
        fail('expected RuntimeConfigError');
      } on RuntimeConfigError catch (error) {
        expect(error.invalidVariables, contains('NUBERUSH_API_BASE_URL'));
        expect(error.message, isNot(contains(secretishValue)));
        expect(error.toString(), isNot(contains(secretishValue)));
      }
    });

    test('reports all offending variables together', () {
      try {
        RuntimeConfig.fromValues(
          apiBaseUrl: '',
          supabaseUrl: '',
          supabaseAnonKey: '',
        );
        fail('expected RuntimeConfigError');
      } on RuntimeConfigError catch (error) {
        expect(error.invalidVariables, containsAll(kRequiredRuntimeVariables));
      }
    });
  });
}
