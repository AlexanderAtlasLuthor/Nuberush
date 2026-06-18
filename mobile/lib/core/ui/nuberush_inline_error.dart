// NubeRush Driver — inline error banner (Dr.1.4.B).
//
// Renders a safe, user-facing error message in brand danger styling. It only
// ever shows the [message] string it is given — callers are responsible for
// mapping raw backend/Supabase errors to safe copy before passing them here
// (the contract forbids rendering raw errors). No auth, no backend.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';
import '../theme/nuberush_radii.dart';
import '../theme/nuberush_spacing.dart';

class NubeRushInlineError extends StatelessWidget {
  const NubeRushInlineError({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(NubeRushSpacing.md),
      decoration: BoxDecoration(
        // Tinted danger surface; opaque-blended for the dark background.
        color: const Color(0x22EF4444),
        borderRadius: NubeRushRadii.borderMd,
        border: Border.all(color: NubeRushColors.danger),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: NubeRushColors.danger,
              size: 20),
          const SizedBox(width: NubeRushSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: NubeRushColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}
