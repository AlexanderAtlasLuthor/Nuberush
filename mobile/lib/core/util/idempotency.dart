// NubeRush Driver — client-side idempotency keys (Dr.1.3.H).
//
// Compliance actions (verify-age / proof / complete / fail / return-to-store)
// accept an optional `Idempotency-Key` header (backend Dr.1.2.I ledger). The
// client generates a fresh key per user-triggered ATTEMPT so an accidental
// double-submit of the same attempt is de-duplicated server-side, while a
// deliberate retry after a failure is a new attempt with a new key.
//
// No secrets, no PII — just an opaque unique token. The generator is injectable
// so tests can supply deterministic keys.

import 'dart:math';

/// Produces a unique idempotency key per call.
typedef IdempotencyKeyGenerator = String Function();

final Random _rng = Random();

/// Default opaque key: time component + random suffix. Unique per call without
/// adding a uuid dependency. Not security-sensitive.
String defaultIdempotencyKey() {
  final int micros = DateTime.now().microsecondsSinceEpoch;
  final int rand = _rng.nextInt(1 << 32);
  return 'ndk-${micros.toRadixString(16)}-${rand.toRadixString(16)}';
}
