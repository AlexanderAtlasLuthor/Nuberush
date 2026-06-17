// NubeRush Driver — auth/session foundation (Dr.1.3.D).
//
// Wraps Supabase Auth behind a small app-owned interface so screens never call
// Supabase directly (mirrors web/src/api/session-token.ts conceptually). The
// Supabase session is the source of truth; token reads are LIVE (never
// stale-cached), and sign-out clears both the Supabase session and the secure
// token store.
//
// Testability: the Supabase surface is reduced to a tiny [SupabaseAuthGateway]
// port. Unit tests inject a fake gateway and never touch real Supabase. The
// real adapter ([GoTrueAuthGateway]) wraps the GoTrue client and is wired in a
// later runtime-integration step. No token VALUES are ever logged.

import 'package:supabase_flutter/supabase_flutter.dart';

import 'secure_session_store.dart';

/// Minimal authenticated/unauthenticated session state for the UI layer.
enum AuthSessionState { authenticated, unauthenticated }

/// App-owned auth/session interface. Screens depend on this, not on Supabase.
abstract class AuthSession {
  /// The current access token from the live session, or `null` when there is
  /// no session. Always reads fresh — no module-level caching.
  Future<String?> getAccessToken();

  /// Emits the session state on every auth change.
  Stream<AuthSessionState> get authStateChanges;

  /// End the session: sign out of Supabase and clear secure storage.
  Future<void> signOut();
}

/// Tiny port over the Supabase auth surface this app actually uses. Keeps
/// [SupabaseAuthSession] unit-testable without a real Supabase client.
abstract class SupabaseAuthGateway {
  /// Current access token from the live session, or `null`.
  String? get currentAccessToken;

  /// Emits the access token (or `null`) on each auth state change.
  Stream<String?> get onAccessTokenChanged;

  /// End the Supabase session.
  Future<void> signOut();
}

/// [AuthSession] backed by a [SupabaseAuthGateway] and a [SecureSessionStore].
class SupabaseAuthSession implements AuthSession {
  SupabaseAuthSession({
    required SupabaseAuthGateway gateway,
    required SecureSessionStore secureStore,
  })  : _gateway = gateway,
        _secureStore = secureStore;

  final SupabaseAuthGateway _gateway;
  final SecureSessionStore _secureStore;

  @override
  Future<String?> getAccessToken() async {
    final String? token = _gateway.currentAccessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  @override
  Stream<AuthSessionState> get authStateChanges =>
      _gateway.onAccessTokenChanged.map(
        (String? token) => (token != null && token.isNotEmpty)
            ? AuthSessionState.authenticated
            : AuthSessionState.unauthenticated,
      );

  @override
  Future<void> signOut() async {
    // Sign out of Supabase first, then clear our secure boundary. Both run
    // even if the UI is already unauthenticated (idempotent).
    await _gateway.signOut();
    await _secureStore.clear();
  }
}

/// Real [SupabaseAuthGateway] adapter over the GoTrue auth client.
///
/// Wired during runtime integration (after `Supabase.initialize(...)`), e.g.
/// `GoTrueAuthGateway(Supabase.instance.client.auth)`. Not exercised by unit
/// tests, which use a fake gateway instead.
class GoTrueAuthGateway implements SupabaseAuthGateway {
  GoTrueAuthGateway(this._auth);

  final GoTrueClient _auth;

  @override
  String? get currentAccessToken => _auth.currentSession?.accessToken;

  @override
  Stream<String?> get onAccessTokenChanged =>
      _auth.onAuthStateChange.map((AuthState state) => state.session?.accessToken);

  @override
  Future<void> signOut() => _auth.signOut();
}
