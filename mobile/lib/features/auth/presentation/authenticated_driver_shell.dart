// NubeRush Driver — authenticated app shell (Dr.1.4.E).
//
// Hosts the existing read-only Driver Home (DriverHomeBootstrap) once the user
// is authenticated and surfaces a reusable LogoutButton in the home app bar.
// It preserves the existing Navigator.push driver flows untouched — it only
// adds the logout affordance. No ApiClient/token wiring and no 401/403 policy
// here (Dr.1.4.F).

import 'package:flutter/material.dart';

import '../../../app/router.dart';
import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../driver/data/driver_repository.dart';
import 'logout_button.dart';

class AuthenticatedDriverShell extends StatelessWidget {
  const AuthenticatedDriverShell({
    super.key,
    required this.controller,
    this.onSignedOut,
    this.repository,
  });

  final AuthController controller;

  /// Optional hook after a successful sign-out. The AuthGate also reacts to the
  /// Supabase auth-state stream, so routing back to login is automatic.
  final VoidCallback? onSignedOut;

  /// Live, token-wired driver repository forwarded to [DriverHomeBootstrap].
  /// When null, the legacy env-built repository is used.
  final DriverReadRepository? repository;

  @override
  Widget build(BuildContext context) {
    return DriverHomeBootstrap(
      repository: repository,
      appBarActions: [
        Padding(
          padding: const EdgeInsets.only(right: NubeRushSpacing.sm),
          child: Center(
            child: LogoutButton(
              controller: controller,
              onSignedOut: onSignedOut,
            ),
          ),
        ),
      ],
    );
  }
}
