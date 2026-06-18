// NubeRush Driver — primary action button (Dr.1.4.B).
//
// Brand-orange filled button with enabled / disabled / loading states. Pure
// presentation: no auth, no backend. Reusable by the future LoginScreen.
//
// When [isLoading] is true the button is disabled and shows a small spinner in
// place of the label, so callers can reflect in-flight actions without wiring
// any business logic here.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';

class NubeRushPrimaryButton extends StatelessWidget {
  const NubeRushPrimaryButton({
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
    return FilledButton(
      onPressed: _enabled ? onPressed : null,
      child: isLoading
          ? const SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor:
                    AlwaysStoppedAnimation<Color>(NubeRushColors.onPrimary),
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
