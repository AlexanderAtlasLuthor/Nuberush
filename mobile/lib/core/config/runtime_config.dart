// NubeRush Driver — central runtime configuration (Dr.1.4.C).
//
// Aggregates the two existing public-config validators (ApiConfig +
// SupabaseConfig) into one object the app bootstrap resolves once at startup.
// All three required PUBLIC variables are validated together:
//   NUBERUSH_API_BASE_URL
//   NUBERUSH_SUPABASE_URL
//   NUBERUSH_SUPABASE_ANON_KEY
//
// A missing/invalid value is a typed, user-safe failure: [RuntimeConfigError]
// lists only the affected VARIABLE NAMES — never their values, never a secret,
// never a raw exception/stack trace. No localhost fallback, no network call.

import '../api/api_config.dart';
import 'environment.dart';
import 'supabase_config.dart';

/// Canonical names of the required public runtime variables, in display order.
const List<String> kRequiredRuntimeVariables = <String>[
  'NUBERUSH_API_BASE_URL',
  'NUBERUSH_SUPABASE_URL',
  'NUBERUSH_SUPABASE_ANON_KEY',
];

/// Thrown when one or more required public runtime variables are
/// missing or invalid. Carries variable NAMES only (no values/secrets).
class RuntimeConfigError implements Exception {
  const RuntimeConfigError(this.invalidVariables);

  /// Names of the variables that are missing or invalid (subset of
  /// [kRequiredRuntimeVariables]). Never contains values.
  final List<String> invalidVariables;

  /// Fixed, user-safe message. Contains no values, secrets, or stack traces.
  String get message =>
      'Required public runtime configuration is missing or invalid.';

  @override
  String toString() =>
      'RuntimeConfigError: $message (variables: ${invalidVariables.join(', ')})';
}

/// Resolved, validated runtime configuration for the app.
class RuntimeConfig {
  RuntimeConfig._({required this.apiConfig, required this.supabaseConfig});

  final ApiConfig apiConfig;
  final SupabaseConfig supabaseConfig;

  /// Resolve from the compile-time environment (`--dart-define`).
  factory RuntimeConfig.fromEnvironment() => RuntimeConfig.fromValues(
        apiBaseUrl: Environment.apiBaseUrl,
        supabaseUrl: Environment.supabaseUrl,
        supabaseAnonKey: Environment.supabaseAnonKey,
      );

  /// Resolve from explicit values — the test seam (no env vars required).
  ///
  /// Validates every variable and, on any failure, throws a single
  /// [RuntimeConfigError] naming all offending variables so the UI can list
  /// them. Values are never echoed back.
  factory RuntimeConfig.fromValues({
    required String apiBaseUrl,
    required String supabaseUrl,
    required String supabaseAnonKey,
  }) {
    final invalid = <String>[];

    ApiConfig? apiConfig;
    try {
      apiConfig = ApiConfig.fromBaseUrl(apiBaseUrl);
    } on ApiConfigError {
      invalid.add('NUBERUSH_API_BASE_URL');
    }

    // SupabaseConfig validates URL + anon key together. Determine precisely
    // which variable failed without leaking values: the anon key only fails
    // when blank, so a non-blank-pair failure can only be an invalid URL.
    SupabaseConfig? supabaseConfig;
    final bool urlBlank = supabaseUrl.trim().isEmpty;
    final bool keyBlank = supabaseAnonKey.trim().isEmpty;
    if (urlBlank) invalid.add('NUBERUSH_SUPABASE_URL');
    if (keyBlank) invalid.add('NUBERUSH_SUPABASE_ANON_KEY');
    if (!urlBlank && !keyBlank) {
      try {
        supabaseConfig = SupabaseConfig.fromValues(
          url: supabaseUrl,
          anonKey: supabaseAnonKey,
        );
      } on SupabaseConfigError {
        // Both non-blank → the only remaining failure is an invalid URL.
        invalid.add('NUBERUSH_SUPABASE_URL');
      }
    }

    if (invalid.isNotEmpty || apiConfig == null || supabaseConfig == null) {
      throw RuntimeConfigError(List<String>.unmodifiable(invalid));
    }

    return RuntimeConfig._(
      apiConfig: apiConfig,
      supabaseConfig: supabaseConfig,
    );
  }
}
