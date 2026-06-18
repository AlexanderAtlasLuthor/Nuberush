// NubeRush Driver — auth loading state (Dr.1.4.E).
//
// Branded, safe loading surface shown while the session is being restored at
// launch (before we know authenticated vs unauthenticated). No network call of
// its own; pure presentation built from the Dr.1.4.B primitives.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class AuthLoadingScreen extends StatelessWidget {
  const AuthLoadingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const NubeRushScaffold(
      padding: EdgeInsets.all(NubeRushSpacing.xl),
      body: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Center(child: NubeRushBrandHeader()),
          SizedBox(height: NubeRushSpacing.xxl),
          NubeRushLoadingState(message: 'Restoring your session…'),
        ],
      ),
    );
  }
}
