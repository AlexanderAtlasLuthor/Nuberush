// NubeRush Driver — auth gate (Dr.1.4.E).
//
// The runtime decision point between unauthenticated and authenticated app
// trees. On launch it restores the current session (via AuthSession) and then
// follows the Supabase auth-state stream:
//   - resolving      -> AuthLoadingScreen
//   - unauthenticated -> LoginScreen
//   - authenticated   -> AuthenticatedDriverShell (Driver Home + logout)
//
// Login/logout transitions are driven by the stream, so a successful sign-in or
// sign-out automatically swaps the tree. No ApiClient/token wiring and no
// 401/403 policy here (Dr.1.4.F).

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/auth/auth_session.dart';
import '../../driver/data/driver_repository.dart';
import 'auth_loading_screen.dart';
import 'authenticated_driver_shell.dart';
import 'login_screen.dart';

class AuthGate extends StatefulWidget {
  const AuthGate({
    super.key,
    required this.session,
    required this.controller,
    this.repository,
  });

  final AuthSession session;
  final AuthController controller;

  /// Live, token-wired driver repository forwarded to the authenticated shell.
  /// When null, the shell falls back to the legacy env-built repository.
  final DriverReadRepository? repository;

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  StreamSubscription<AuthSessionState>? _subscription;

  /// Null while the initial session restore is in flight (loading state).
  AuthSessionState? _state;

  @override
  void initState() {
    super.initState();
    // Follow live auth changes (login/logout/refresh) authoritatively...
    _subscription = widget.session.authStateChanges.listen(_onState);
    // ...and resolve the current session once at launch for fast restore.
    _restoreInitialSession();
  }

  void _onState(AuthSessionState state) {
    if (!mounted) return;
    setState(() => _state = state);
  }

  Future<void> _restoreInitialSession() async {
    final String? token = await widget.session.getAccessToken();
    if (!mounted) return;
    // Only seed the initial value if the stream hasn't already delivered one.
    setState(() {
      _state ??= (token != null && token.isNotEmpty)
          ? AuthSessionState.authenticated
          : AuthSessionState.unauthenticated;
    });
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    switch (_state) {
      case null:
        return const AuthLoadingScreen();
      case AuthSessionState.authenticated:
        return AuthenticatedDriverShell(
          controller: widget.controller,
          repository: widget.repository,
        );
      case AuthSessionState.unauthenticated:
        return LoginScreen(controller: widget.controller);
    }
  }
}
