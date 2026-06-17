// NubeRush Driver — typed API error model (Dr.1.3.C).
//
// Mirrors the web client's transport-error semantics conceptually (see
// web/src/api/errors.ts + the readErrorPayload logic in web/src/api/client.ts),
// NOT its UI. Every non-2xx response and every transport failure is normalized
// to an [ApiError] before it bubbles out of the API client.
//
// Compatible with FastAPI's two error shapes:
//   - HTTPException          -> { "detail": "<string>" }
//   - Pydantic ValidationError -> { "detail": [ { "loc": [...], "msg": "...",
//                                               "type": "..." } ] }
// plus generic JSON, plain-text, and empty bodies. Network/transport failures
// are represented with status 0.

import 'dart:convert';

/// Default user-safe message for a non-2xx response with no usable body.
const String _kFallbackMessage = 'Request failed';

/// Default user-safe message for a transport/network failure (status 0).
const String _kNetworkMessage = 'Network request failed';

/// Typed error for any API failure surfaced by the core client.
///
/// [status] is the HTTP status code, or `0` for network/transport failures.
/// [message] is always a user-safe, deterministic string. [details] holds the
/// parsed payload when available (never guaranteed to be sensitive-free by the
/// backend, so callers should not render it verbatim). [code] is an optional
/// application-level error code when the backend supplies one.
class ApiError implements Exception {
  const ApiError({
    required this.status,
    required this.message,
    this.details,
    this.code,
  });

  /// Build an [ApiError] from a transport/network failure (no HTTP response).
  factory ApiError.network([String? message]) {
    return ApiError(status: 0, message: message ?? _kNetworkMessage);
  }

  /// Normalize a non-2xx HTTP response into an [ApiError].
  ///
  /// [status] is the response status code. [body] is the raw response body
  /// (may be empty). Parsing is best-effort and never throws.
  factory ApiError.fromResponse({required int status, required String body}) {
    final String fallback = status == 0 ? _kNetworkMessage : _kFallbackMessage;

    final String trimmed = body.trim();
    if (trimmed.isEmpty) {
      return ApiError(status: status, message: fallback);
    }

    Object? parsed;
    try {
      parsed = jsonDecode(trimmed);
    } catch (_) {
      // Body was not JSON (HTML 502 page, plain text, etc.). Use the raw text
      // as the message but keep it bounded so we never dump a huge payload.
      return ApiError(
        status: status,
        message: _boundedText(trimmed, fallback),
      );
    }

    if (parsed is Map<String, dynamic>) {
      final String message = _messageFromJsonMap(parsed) ?? fallback;
      final Object? code = parsed['code'];
      return ApiError(
        status: status,
        message: message,
        details: parsed,
        code: code is String ? code : null,
      );
    }

    // Valid JSON but not an object (array, number, string literal, ...).
    return ApiError(status: status, message: fallback, details: parsed);
  }

  /// HTTP status code; `0` for network/transport failures.
  final int status;

  /// User-safe, deterministic message.
  final String message;

  /// Parsed error payload when available.
  final Object? details;

  /// Application-level error code when the backend supplies one.
  final String? code;

  /// Extract a message from a FastAPI-style JSON error object.
  ///
  /// Handles `{ "detail": "..." }`, `{ "detail": [ { "msg": "..." } ] }`, and
  /// `{ "message": "..." }`. Returns `null` when no usable message is found.
  static String? _messageFromJsonMap(Map<String, dynamic> obj) {
    final Object? detail = obj['detail'];

    // FastAPI HTTPException: { "detail": "<string>" }
    if (detail is String && detail.trim().isNotEmpty) {
      return detail;
    }

    // Pydantic ValidationError: { "detail": [ { "msg": "...", ... }, ... ] }
    if (detail is List && detail.isNotEmpty) {
      final Object? first = detail.first;
      if (first is Map) {
        final Object? msg = first['msg'];
        if (msg is String && msg.trim().isNotEmpty) {
          return msg;
        }
      }
    }

    // Generic JSON: { "message": "<string>" }
    final Object? message = obj['message'];
    if (message is String && message.trim().isNotEmpty) {
      return message;
    }

    return null;
  }

  /// Keep a plain-text body short so an error message never dumps a full page.
  static String _boundedText(String text, String fallback) {
    if (text.isEmpty) return fallback;
    const int maxLen = 200;
    if (text.length <= maxLen) return text;
    return '${text.substring(0, maxLen)}…';
  }

  @override
  String toString() => 'ApiError(status: $status, message: $message'
      '${code != null ? ', code: $code' : ''})';

  @override
  bool operator ==(Object other) =>
      other is ApiError &&
      other.status == status &&
      other.message == message &&
      other.code == code;

  @override
  int get hashCode => Object.hash(status, message, code);
}
