// NubeRush Driver — brand color tokens (Dr.1.4.B).
//
// Single source of truth for the NubeRush mobile palette. Values are ported
// from the web app's design tokens (web/src/index.css) so the Driver App,
// Web App and future Customer App read as one ecosystem: a premium dark
// navy/near-black surface with a warm orange primary/accent.
//
// HSL → ARGB conversions of the web tokens:
//   --background        240  7%  3%  -> 0xFF070709 (near-black navy)
//   --card              240 14%  9%  -> 0xFF14141A (dark card surface)
//   --secondary         240 10% 14%  -> 0xFF1C1C24 (elevated/glass surface)
//   --muted             240  8% 18%  -> 0xFF26262E (muted fill)
//   --foreground         30 25% 93%  -> 0xFFF2EDE9 (near-white text)
//   --muted-foreground  220 10% 50%  -> 0xFF737B8C (muted gray text)
//   --primary            18 100% 59% -> 0xFFFF6D2E (NubeRush orange)
//   --border            240 10% 16%  -> 0xFF25252D (muted border)
//   --destructive         0 84% 60%  -> 0xFFEF4444 (danger)
//   --success           142 71% 45%  -> 0xFF22C55E (success)
//
// Do NOT hardcode these colors in screens/components — always reference this
// class (directly or via the central ThemeData built in nuberush_theme.dart).

import 'package:flutter/material.dart';

/// NubeRush brand palette. All values are opaque ARGB unless noted.
abstract final class NubeRushColors {
  NubeRushColors._();

  // --- Surfaces ---------------------------------------------------------

  /// App background: dark navy / near-black.
  static const Color background = Color(0xFF070709);

  /// Default card / panel surface.
  static const Color surface = Color(0xFF14141A);

  /// Elevated / glass-like surface (dialogs, raised cards, app bar).
  static const Color surfaceElevated = Color(0xFF1C1C24);

  /// Muted fill used for inputs and subtle chips.
  static const Color surfaceMuted = Color(0xFF26262E);

  /// Muted border / hairline divider.
  static const Color border = Color(0xFF25252D);

  // --- Brand / accents --------------------------------------------------

  /// Primary brand orange (buttons, accents, active states).
  static const Color primary = Color(0xFFFF6D2E);

  /// Deeper orange for pressed/secondary emphasis and gradients.
  static const Color primaryDeep = Color(0xFFE85518);

  /// Lighter orange used at the top of the brand-mark gradient.
  static const Color primaryLight = Color(0xFFFF8B4A);

  /// Focus outline / accent ring (mirrors --ring).
  static const Color focus = primary;

  // --- Text -------------------------------------------------------------

  /// Primary text: warm near-white.
  static const Color textPrimary = Color(0xFFF2EDE9);

  /// Secondary text: muted gray.
  static const Color textSecondary = Color(0xFF737B8C);

  /// Text/icon color rendered on top of the primary orange.
  static const Color onPrimary = Color(0xFFFFFFFF);

  // --- Status -----------------------------------------------------------

  /// Danger / destructive.
  static const Color danger = Color(0xFFEF4444);

  /// Success / positive.
  static const Color success = Color(0xFF22C55E);

  // --- State ------------------------------------------------------------

  /// Disabled foreground/fill.
  static const Color disabled = Color(0xFF3A3A44);

  /// Gradient stops for the brand mark (light -> deep orange).
  static const List<Color> brandGradient = <Color>[primaryLight, primaryDeep];
}
