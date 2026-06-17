// NubeRush Driver — API client configuration (Dr.1.3.C).
//
// Mirrors web/src/api/config.ts conceptually: a single place that resolves the
// FastAPI backend base URL from the public, client-safe `--dart-define`
// (NUBERUSH_API_BASE_URL). No secrets, no network calls — pure data.
//
// Unlike the web build (which falls back to localhost in dev), the mobile app
// has no implicit default origin: a missing or invalid base URL is a hard,
// typed configuration error so a build can never silently ship a broken or
// localhost endpoint to a driver's device.

import '../config/environment.dart';

/// Thrown when API configuration is missing or invalid.
class ApiConfigError implements Exception {
  const ApiConfigError(this.message);

  final String message;

  @override
  String toString() => 'ApiConfigError: $message';
}

/// Resolved, validated API configuration.
class ApiConfig {
  ApiConfig._(this.baseUri);

  /// Normalized backend base URI (no trailing slash on the path).
  final Uri baseUri;

  /// Resolve configuration from the compile-time environment.
  ///
  /// Reads [Environment.apiBaseUrl] (NUBERUSH_API_BASE_URL). Throws
  /// [ApiConfigError] when unset or invalid.
  factory ApiConfig.fromEnvironment() =>
      ApiConfig.fromBaseUrl(Environment.apiBaseUrl);

  /// Resolve configuration from an explicit base URL string.
  ///
  /// Trailing slashes are stripped. Blank, relative, or non-http(s) values are
  /// rejected with [ApiConfigError] so callers get a deterministic failure.
  /// This is the seam tests use to construct a config without env vars.
  factory ApiConfig.fromBaseUrl(String value) {
    final String trimmed = value.trim();
    if (trimmed.isEmpty) {
      throw const ApiConfigError(
        'NUBERUSH_API_BASE_URL is not set. Provide it via --dart-define.',
      );
    }

    final Uri? parsed = Uri.tryParse(trimmed);
    if (parsed == null ||
        !parsed.hasScheme ||
        (parsed.scheme != 'http' && parsed.scheme != 'https') ||
        !parsed.hasAuthority) {
      throw ApiConfigError('Invalid API base URL: "$value".');
    }

    // Strip trailing slashes from the path so path joining never produces "//".
    // Rebuild the URI from its parts so any base-level query/fragment is
    // dropped cleanly (per-request paths own query strings) without leaving a
    // dangling "?" or "#".
    final String normalizedPath = parsed.path.replaceAll(RegExp(r'/+$'), '');
    final Uri normalized = Uri(
      scheme: parsed.scheme,
      host: parsed.host,
      port: parsed.hasPort ? parsed.port : null,
      path: normalizedPath,
    );

    return ApiConfig._(normalized);
  }
}
