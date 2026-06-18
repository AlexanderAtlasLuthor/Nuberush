// NubeRush Driver — corner radius tokens (Dr.1.4.B).
//
// Central radius scale. The premium NubeRush feel uses generous rounding
// (web --radius: 1rem ≈ 16). Components reference these instead of inlining
// BorderRadius values.

import 'package:flutter/widgets.dart';

abstract final class NubeRushRadii {
  NubeRushRadii._();

  /// 8 — small controls / chips.
  static const double sm = 8;

  /// 12 — buttons / inputs.
  static const double md = 12;

  /// 16 — cards / dialogs (matches web --radius).
  static const double lg = 16;

  /// 24 — large panels / sheets.
  static const double xl = 24;

  /// Pill / fully-rounded.
  static const double pill = 999;

  static const BorderRadius borderSm = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius borderMd = BorderRadius.all(Radius.circular(md));
  static const BorderRadius borderLg = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius borderXl = BorderRadius.all(Radius.circular(xl));
}
