// NubeRush Driver — minimal login/logout interaction state (Dr.1.4.D).
//
// Models ONLY the explicit login/logout interaction for the UI. It is NOT
// session restore and NOT an authStateChanges listener (those arrive in
// Dr.1.4.E). It deliberately stores no password, no token, and no raw
// Supabase/backend exception — only a safe, user-facing [errorMessage].

import 'package:flutter/foundation.dart';

/// Phase of the explicit login/logout interaction.
enum AuthStatus {
  /// No in-flight action; not signed in (initial + after sign-out).
  unauthenticated,

  /// A sign-in or sign-out call is in flight.
  submitting,

  /// The last sign-in succeeded.
  authenticated,

  /// The last action failed; [AuthState.errorMessage] holds safe copy.
  failure,
}

@immutable
class AuthState {
  const AuthState._(this.status, this.errorMessage);

  const AuthState.unauthenticated()
      : this._(AuthStatus.unauthenticated, null);
  const AuthState.submitting() : this._(AuthStatus.submitting, null);
  const AuthState.authenticated() : this._(AuthStatus.authenticated, null);

  /// A failure carrying a SAFE, user-facing message only (never a raw error).
  const AuthState.failure(String message)
      : this._(AuthStatus.failure, message);

  final AuthStatus status;

  /// Safe, user-facing error message — present only on [AuthStatus.failure].
  final String? errorMessage;

  bool get isSubmitting => status == AuthStatus.submitting;
  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get hasError => status == AuthStatus.failure;

  @override
  bool operator ==(Object other) =>
      other is AuthState &&
      other.status == status &&
      other.errorMessage == errorMessage;

  @override
  int get hashCode => Object.hash(status, errorMessage);

  @override
  String toString() => 'AuthState($status, errorMessage: $errorMessage)';
}
