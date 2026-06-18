// NubeRush Driver — spacing tokens (Dr.1.4.B).
//
// Central spacing scale so screens/components use consistent rhythm instead of
// ad-hoc magic numbers. Multiples of 4 to match the web app's spacing feel.

abstract final class NubeRushSpacing {
  NubeRushSpacing._();

  /// 4 — hairline gaps.
  static const double xs = 4;

  /// 8 — tight gaps.
  static const double sm = 8;

  /// 12 — compact padding.
  static const double md = 12;

  /// 16 — default content padding.
  static const double lg = 16;

  /// 24 — section padding / screen gutters.
  static const double xl = 24;

  /// 32 — large vertical rhythm.
  static const double xxl = 32;
}
