// NubeRush Driver — app bootstrap tests (Dr.1.4.C).

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app_bootstrap.dart';
import 'package:nuberush_driver/core/config/runtime_config.dart';

RuntimeConfig _validConfig() => RuntimeConfig.fromValues(
      apiBaseUrl: 'https://api.nuberush.test',
      supabaseUrl: 'https://project.supabase.test',
      supabaseAnonKey: 'public-anon-key-value',
    );

void main() {
  group('bootstrapApp', () {
    test('valid config initializes Supabase exactly once and returns ready',
        () async {
      var initCalls = 0;
      RuntimeConfig? initializedWith;

      final state = await bootstrapApp(
        configLoader: _validConfig,
        supabaseInitializer: (config) async {
          initCalls++;
          initializedWith = config;
        },
      );

      expect(initCalls, 1);
      expect(state, isA<AppBootstrapReady>());
      expect((state as AppBootstrapReady).config, same(initializedWith));
    });

    test('invalid config does NOT initialize Supabase', () async {
      var initCalls = 0;

      final state = await bootstrapApp(
        configLoader: () => throw const RuntimeConfigError(
          ['NUBERUSH_API_BASE_URL'],
        ),
        supabaseInitializer: (_) async => initCalls++,
      );

      expect(initCalls, 0);
      expect(state, isA<AppBootstrapConfigFailure>());
    });

    test('invalid config returns a failure carrying the variable names',
        () async {
      final state = await bootstrapApp(
        configLoader: () => throw const RuntimeConfigError(
          ['NUBERUSH_SUPABASE_URL', 'NUBERUSH_SUPABASE_ANON_KEY'],
        ),
        supabaseInitializer: (_) async {},
      );

      expect(state, isA<AppBootstrapConfigFailure>());
      expect(
        (state as AppBootstrapConfigFailure).invalidVariables,
        containsAll(['NUBERUSH_SUPABASE_URL', 'NUBERUSH_SUPABASE_ANON_KEY']),
      );
    });
  });
}
