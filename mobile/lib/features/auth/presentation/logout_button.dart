// NubeRush Driver — reusable sign-out button (Dr.1.4.D).
//
// Drives an injected [AuthController.signOut] and calls back via [onSignedOut]
// on success. Shows an in-flight loading state and, on failure, a safe SnackBar
// message. It performs NO root navigation and NO session restore (Dr.1.4.E),
// and logs no token.

import 'package:flutter/material.dart';

import '../../../core/auth/auth_controller.dart';

class LogoutButton extends StatefulWidget {
  const LogoutButton({
    super.key,
    required this.controller,
    this.onSignedOut,
    this.label = 'Sign out',
  });

  final AuthController controller;

  /// Called after a successful sign-out. Root routing is wired in Dr.1.4.E.
  final VoidCallback? onSignedOut;

  final String label;

  @override
  State<LogoutButton> createState() => _LogoutButtonState();
}

class _LogoutButtonState extends State<LogoutButton> {
  bool _busy = false;

  Future<void> _handle() async {
    setState(() => _busy = true);
    final ok = await widget.controller.signOut();
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      widget.onSignedOut?.call();
    } else {
      final message =
          widget.controller.state.errorMessage ?? 'Could not sign out.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_busy) {
      return const OutlinedButton(
        key: Key('logout-button-loading'),
        onPressed: null,
        child: SizedBox(
          height: 20,
          width: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }
    return OutlinedButton.icon(
      key: const Key('logout-button'),
      onPressed: _handle,
      icon: const Icon(Icons.logout, size: 18),
      label: Text(widget.label),
    );
  }
}
