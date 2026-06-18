// NubeRush Driver — secondary action button (Dr.1.4.B).
//
// Outlined, lower-emphasis companion to [NubeRushPrimaryButton]. Pure
// presentation: no auth, no backend.

import 'package:flutter/material.dart';

class NubeRushSecondaryButton extends StatelessWidget {
  const NubeRushSecondaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onPressed,
      child: Row(
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
