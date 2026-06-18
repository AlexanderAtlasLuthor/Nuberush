// NubeRush Driver — login/logout controller (Dr.1.4.D).
//
// Owns the explicit email/password sign-in and sign-out interaction and the
// resulting [AuthState]. Screens depend on this; they never touch Supabase
// directly. This subphase is UI/control ONLY: there is no session restore, no
// authStateChanges listener, no ApiClient/token wiring, and no 401/403 policy
// here (Dr.1.4.E–F).
//
// Safety: the controller never stores the password, never exposes a token, and
// never surfaces a raw Supabase/backend exception — every failure is mapped to
// a fixed, user-safe message. No token/password/error logging.

import 'package:flutter/foundation.dart';
// Only GoTrueClient is needed; `show` avoids a name clash with this app's
// own AuthState (supabase_flutter also exports a class named AuthState).
import 'package:supabase_flutter/supabase_flutter.dart' show GoTrueClient;

import 'auth_session.dart';
import 'auth_state.dart';

/// Safe, user-facing copy. Centralized so no raw error ever reaches the UI.
const String _kInvalidFields = 'Enter your email and password.';
const String _kSignInFailed =
    'Could not sign in. Check your email and password and try again.';
const String _kSignOutFailed = 'Could not sign out. Please try again.';

/// Minimal auth actions the controller needs. Owned by this layer so it can be
/// faked in tests without a real Supabase client. The real adapter
/// ([SupabaseAuthActions]) wraps GoTrue for sign-in and reuses the existing
/// [AuthSession.signOut] for sign-out.
abstract class AuthActions {
  Future<void> signInWithPassword({
    required String email,
    required String password,
  });

  Future<void> signOut();
}

/// Real [AuthActions] adapter: GoTrue for sign-in, [AuthSession] for sign-out.
///
/// Wired during runtime integration (Dr.1.4.E), e.g. from
/// `Supabase.instance.client.auth` + the app's [SupabaseAuthSession]. Not
/// exercised by unit tests, which inject a fake [AuthActions].
class SupabaseAuthActions implements AuthActions {
  SupabaseAuthActions({required GoTrueClient auth, required AuthSession session})
      : _auth = auth,
        _session = session;

  final GoTrueClient _auth;
  final AuthSession _session;

  @override
  Future<void> signInWithPassword({
    required String email,
    required String password,
  }) async {
    await _auth.signInWithPassword(email: email, password: password);
  }

  // Reuses the existing AuthSession.signOut (clears Supabase + secure store).
  @override
  Future<void> signOut() => _session.signOut();
}

/// Drives the explicit login/logout interaction and exposes [AuthState].
class AuthController extends ChangeNotifier {
  AuthController(this._actions);

  final AuthActions _actions;

  AuthState _state = const AuthState.unauthenticated();
  AuthState get state => _state;

  void _set(AuthState next) {
    _state = next;
    notifyListeners();
  }

  /// Attempt an email/password sign-in. Returns true on success.
  ///
  /// Empty fields fail locally (no network). The password is never stored on
  /// the controller; any thrown error is mapped to safe copy.
  Future<bool> signInWithPassword({
    required String email,
    required String password,
  }) async {
    final String normalizedEmail = email.trim();
    if (normalizedEmail.isEmpty || password.isEmpty) {
      _set(const AuthState.failure(_kInvalidFields));
      return false;
    }

    _set(const AuthState.submitting());
    try {
      await _actions.signInWithPassword(
        email: normalizedEmail,
        password: password,
      );
      _set(const AuthState.authenticated());
      return true;
    } catch (_) {
      // Never surface or log the raw error.
      _set(const AuthState.failure(_kSignInFailed));
      return false;
    }
  }

  /// Sign out. Returns true on success.
  Future<bool> signOut() async {
    _set(const AuthState.submitting());
    try {
      await _actions.signOut();
      _set(const AuthState.unauthenticated());
      return true;
    } catch (_) {
      _set(const AuthState.failure(_kSignOutFailed));
      return false;
    }
  }
}
