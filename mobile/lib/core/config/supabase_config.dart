// NubeRush Driver — Supabase public configuration (Dr.1.3.D).
//
// Resolves and validates the PUBLIC, client-safe Supabase values used to
// initialize the auth client. Mirrors web/src/lib/supabase.ts's "fail loud and
// early" rule: a missing/blank/invalid URL or anon key is a typed error, never
// a silent misconfiguration that surfaces later as confusing 401s.
//
// ONLY public values live here:
//   NUBERUSH_SUPABASE_URL
//   NUBERUSH_SUPABASE_ANON_KEY
// The service-role key and any server-only secret are forbidden in the app.

import 'environment.dart';

/// Thrown when Supabase public configuration is missing or invalid.
class SupabaseConfigError implements Exception {
  const SupabaseConfigError(this.message);

  final String message;

  @override
  String toString() => 'SupabaseConfigError: $message';
}

/// Validated public Supabase configuration.
class SupabaseConfig {
  SupabaseConfig._({required this.url, required this.anonKey});

  /// Supabase project URL (https).
  final Uri url;

  /// Public anon key (browser/client-safe by design).
  final String anonKey;

  /// Resolve from the compile-time environment (`--dart-define`).
  factory SupabaseConfig.fromEnvironment() => SupabaseConfig.fromValues(
        url: Environment.supabaseUrl,
        anonKey: Environment.supabaseAnonKey,
      );

  /// Resolve from explicit values. The test seam — no env vars required.
  factory SupabaseConfig.fromValues({
    required String url,
    required String anonKey,
  }) {
    final String trimmedUrl = url.trim();
    if (trimmedUrl.isEmpty) {
      throw const SupabaseConfigError(
        'NUBERUSH_SUPABASE_URL is not set. Provide it via --dart-define.',
      );
    }

    final Uri? parsed = Uri.tryParse(trimmedUrl);
    if (parsed == null ||
        !parsed.hasScheme ||
        (parsed.scheme != 'http' && parsed.scheme != 'https') ||
        !parsed.hasAuthority) {
      throw SupabaseConfigError('Invalid Supabase URL: "$url".');
    }

    final String trimmedKey = anonKey.trim();
    if (trimmedKey.isEmpty) {
      throw const SupabaseConfigError(
        'NUBERUSH_SUPABASE_ANON_KEY is not set. Provide it via --dart-define.',
      );
    }

    return SupabaseConfig._(url: parsed, anonKey: trimmedKey);
  }
}
