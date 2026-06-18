// NubeRush Driver — secondary action button (Dr.1.4.B; loading state Dr.1.5.D).
//
// Outlined, lower-emphasis companion to [NubeRushPrimaryButton]. Pure
// presentation: no auth, no backend.
//
// When [isLoading] is true the button is disabled and shows a small spinner in
// place of the label, mirroring [NubeRushPrimaryButton] so callers can reflect
// an in-flight action without wiring any business logic here.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';

class NubeRushSecondaryButton extends StatelessWidget {
  const NubeRushSecondaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;

  bool get _enabled => onPressed != null && !isLoading;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: _enabled ? onPressed : null,
      child: isLoading
          ? const SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor:
                    AlwaysStoppedAnimation<Color>(NubeRushColors.textPrimary),
              ),
            )
          : Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 18),
                  const SizedBox(width: 8),
                ],
                Text(label),
              ],
            ),
    );
  }
}
