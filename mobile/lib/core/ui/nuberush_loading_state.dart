// NubeRush Driver — full-area loading state (Dr.1.4.B).
//
// Centered brand spinner with optional label. Pure presentation: no auth,
// no backend.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';
import '../theme/nuberush_spacing.dart';

class NubeRushLoadingState extends StatelessWidget {
  const NubeRushLoadingState({super.key, this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(color: NubeRushColors.primary),
          if (message != null) ...[
            const SizedBox(height: NubeRushSpacing.lg),
            Text(
              message!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: NubeRushColors.textSecondary),
            ),
          ],
        ],
      ),
    );
  }
}
