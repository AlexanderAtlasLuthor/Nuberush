// NubeRush Driver — central app theme (Dr.1.4.B).
//
// Replaces the previous generic Material teal seed with a premium NubeRush
// dark theme. All component themes pull from the brand tokens so existing
// driver screens (which already use Theme.of(context) + stock Material
// widgets) adopt the brand look without per-screen rewrites.
//
// Fonts: no external font dependency is added in Dr.1.4.B. DM Sans is the
// intended brand typeface (see [kNubeRushFutureFontFamily]); until the font
// asset ships, the system font is used so tests don't depend on bundled
// assets. The text *scale/weights* are still defined centrally here.

import 'package:flutter/material.dart';

import 'nuberush_colors.dart';
import 'nuberush_radii.dart';

/// Brand typeface intended for a future asset bump. Left unwired in Dr.1.4.B
/// so no font asset/dependency is introduced; documented for Dr.1.4.G+.
const String kNubeRushFutureFontFamily = 'DM Sans';

/// Builds the NubeRush dark [ThemeData] used by the root app.
abstract final class NubeRushTheme {
  NubeRushTheme._();

  static ThemeData dark() {
    const colorScheme = ColorScheme.dark(
      primary: NubeRushColors.primary,
      onPrimary: NubeRushColors.onPrimary,
      primaryContainer: NubeRushColors.primaryDeep,
      onPrimaryContainer: NubeRushColors.onPrimary,
      secondary: NubeRushColors.primary,
      onSecondary: NubeRushColors.onPrimary,
      surface: NubeRushColors.surface,
      onSurface: NubeRushColors.textPrimary,
      surfaceContainerHighest: NubeRushColors.surfaceElevated,
      onSurfaceVariant: NubeRushColors.textSecondary,
      error: NubeRushColors.danger,
      onError: NubeRushColors.onPrimary,
      outline: NubeRushColors.border,
      outlineVariant: NubeRushColors.border,
    );

    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: NubeRushColors.background,
      canvasColor: NubeRushColors.background,
      dividerColor: NubeRushColors.border,
    );

    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: NubeRushColors.background,
        foregroundColor: NubeRushColors.textPrimary,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: NubeRushColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
        ),
      ),
      cardTheme: CardThemeData(
        color: NubeRushColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: NubeRushRadii.borderLg,
          side: const BorderSide(color: NubeRushColors.border),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: _primaryButtonStyle(),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: _primaryButtonStyle(),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NubeRushColors.textPrimary,
          disabledForegroundColor: NubeRushColors.disabled,
          side: const BorderSide(color: NubeRushColors.border),
          // Min height only; min width 0 so buttons embedded in a Row still
          // size to content. Full-width is opt-in at the call site.
          minimumSize: const Size(0, 52),
          shape: const RoundedRectangleBorder(
            borderRadius: NubeRushRadii.borderMd,
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: NubeRushColors.primary,
          disabledForegroundColor: NubeRushColors.disabled,
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: NubeRushColors.surfaceMuted,
        hintStyle: const TextStyle(color: NubeRushColors.textSecondary),
        labelStyle: const TextStyle(color: NubeRushColors.textSecondary),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: NubeRushRadii.borderMd,
          borderSide: const BorderSide(color: NubeRushColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: NubeRushRadii.borderMd,
          borderSide: const BorderSide(color: NubeRushColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: NubeRushRadii.borderMd,
          borderSide: const BorderSide(color: NubeRushColors.focus, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: NubeRushRadii.borderMd,
          borderSide: const BorderSide(color: NubeRushColors.danger),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: NubeRushRadii.borderMd,
          borderSide: const BorderSide(color: NubeRushColors.danger, width: 2),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: NubeRushColors.surfaceElevated,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: NubeRushRadii.borderLg,
        ),
        titleTextStyle: const TextStyle(
          color: NubeRushColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
        contentTextStyle: const TextStyle(
          color: NubeRushColors.textSecondary,
          fontSize: 15,
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: NubeRushColors.surfaceElevated,
        contentTextStyle: TextStyle(color: NubeRushColors.textPrimary),
        actionTextColor: NubeRushColors.primary,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: NubeRushRadii.borderMd),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: NubeRushColors.primary,
      ),
      dividerTheme: const DividerThemeData(
        color: NubeRushColors.border,
        thickness: 1,
        space: 1,
      ),
      iconTheme: const IconThemeData(color: NubeRushColors.textPrimary),
      textTheme: _textTheme(base.textTheme),
    );
  }

  static ButtonStyle _primaryButtonStyle() {
    return FilledButton.styleFrom(
      backgroundColor: NubeRushColors.primary,
      foregroundColor: NubeRushColors.onPrimary,
      disabledBackgroundColor: NubeRushColors.surfaceMuted,
      disabledForegroundColor: NubeRushColors.disabled,
      // Min height only; min width 0 so buttons embedded in a Row still size
      // to content. Full-width is opt-in at the call site.
      minimumSize: const Size(0, 52),
      shape: const RoundedRectangleBorder(borderRadius: NubeRushRadii.borderMd),
      textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
    );
  }

  static TextTheme _textTheme(TextTheme base) {
    return base.apply(
      bodyColor: NubeRushColors.textPrimary,
      displayColor: NubeRushColors.textPrimary,
    );
  }
}
