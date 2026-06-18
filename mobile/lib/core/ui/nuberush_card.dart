// NubeRush Driver — brand card primitive (Dr.1.4.B).
//
// A premium dark surface with brand border + radius. Pure presentation: no
// auth, no backend, no Supabase. Reusable by driver screens and the future
// LoginScreen (Dr.1.4.D).

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';
import '../theme/nuberush_radii.dart';
import '../theme/nuberush_spacing.dart';

class NubeRushCard extends StatelessWidget {
  const NubeRushCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(NubeRushSpacing.lg),
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = Padding(padding: padding, child: child);
    return Material(
      color: NubeRushColors.surface,
      borderRadius: NubeRushRadii.borderLg,
      child: InkWell(
        onTap: onTap,
        borderRadius: NubeRushRadii.borderLg,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: NubeRushRadii.borderLg,
            border: Border.all(color: NubeRushColors.border),
          ),
          child: content,
        ),
      ),
    );
  }
}
