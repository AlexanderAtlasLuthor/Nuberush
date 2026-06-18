// NubeRush Driver — brand header / wordmark (Dr.1.4.B).
//
// The NubeRush flame-in-a-rounded-orange-box mark plus the wordmark. This is a
// lightweight, asset-free rendition of web/src/components/common/brand-mark.tsx
// (flame glyph on a #FF8B4A -> #FF6B2C gradient tile). No SVG/image asset is
// bundled in Dr.1.4.B; a CustomPaint of the official flame path can replace the
// icon later without changing this widget's API.
//
// Pure presentation: no auth, no backend. Reusable by the future LoginScreen.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';
import '../theme/nuberush_radii.dart';
import '../theme/nuberush_spacing.dart';

class NubeRushBrandHeader extends StatelessWidget {
  const NubeRushBrandHeader({
    super.key,
    this.title = 'NubeRush',
    this.subtitle = 'Driver',
    this.markSize = 44,
  });

  final String title;
  final String? subtitle;
  final double markSize;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _BrandMark(size: markSize),
        const SizedBox(width: NubeRushSpacing.md),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                color: NubeRushColors.textPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
              ),
            ),
            if (subtitle != null)
              Text(
                subtitle!,
                style: const TextStyle(
                  color: NubeRushColors.primary,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 1.5,
                ),
              ),
          ],
        ),
      ],
    );
  }
}

/// The rounded orange gradient tile with a flame glyph — the NubeRush mark.
class _BrandMark extends StatelessWidget {
  const _BrandMark({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: size,
      width: size,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: NubeRushColors.brandGradient,
        ),
        borderRadius: NubeRushRadii.borderMd,
      ),
      child: Icon(
        Icons.local_fire_department,
        color: NubeRushColors.onPrimary,
        size: size * 0.6,
      ),
    );
  }
}
