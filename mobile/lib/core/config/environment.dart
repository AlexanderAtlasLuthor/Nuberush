// NubeRush Driver — environment configuration placeholder.
//
// Dr.1.3.B skeleton: resolves only PUBLIC, client-safe values from
// compile-time `--dart-define`s. No secrets, no network calls, no defaults
// that embed real endpoints. The actual API client (Dr.1.3.C) and Supabase
// auth (Dr.1.3.D) will consume these values.
//
// ALLOWED (public / client-safe):
//   NUBERUSH_API_BASE_URL
//   NUBERUSH_SUPABASE_URL
//   NUBERUSH_SUPABASE_ANON_KEY
//
// FORBIDDEN in mobile config (never read or embed these):
//   DATABASE_URL, Supabase service-role key, Postgres credentials,
//   JWT/private signing secrets, server-only JWKS/private material.

/// Public, client-safe runtime configuration sourced from `--dart-define`.
///
/// Values are read at compile time via [String.fromEnvironment]. Unset values
/// resolve to the empty string; consumers in later subphases decide how to
/// handle a missing value (the skeleton does not).
class Environment {
  const Environment._();

  /// FastAPI backend base URL (e.g. https://api.example.com). Public.
  static const String apiBaseUrl =
      String.fromEnvironment('NUBERUSH_API_BASE_URL');

  /// Supabase project URL. Public.
  static const String supabaseUrl =
      String.fromEnvironment('NUBERUSH_SUPABASE_URL');

  /// Supabase anon (public) key. Public/browser-safe by design.
  static const String supabaseAnonKey =
      String.fromEnvironment('NUBERUSH_SUPABASE_ANON_KEY');
}
