// NubeRush Driver — theme foundation tests (Dr.1.4.B).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/core/theme/nuberush_colors.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';

void main() {
  group('NubeRushTheme', () {
    test('exposes a dark Material 3 theme', () {
      final theme = NubeRushTheme.dark();
      expect(theme.brightness, Brightness.dark);
      expect(theme.useMaterial3, isTrue);
      expect(theme.colorScheme.brightness, Brightness.dark);
    });

    test('uses NubeRush brand tokens, not the old teal seed', () {
      final theme = NubeRushTheme.dark();
      expect(theme.colorScheme.primary, NubeRushColors.primary);
      expect(theme.scaffoldBackgroundColor, NubeRushColors.background);
      expect(theme.colorScheme.surface, NubeRushColors.surface);
    });
  });

  testWidgets('root app applies the NubeRush dark theme', (tester) async {
    await tester.pumpWidget(
      const NubeRushDriverApp(home: Scaffold(body: SizedBox.shrink())),
    );
    await tester.pumpAndSettle();

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.theme, isNotNull);
    expect(app.theme!.brightness, Brightness.dark);
    expect(app.theme!.scaffoldBackgroundColor, NubeRushColors.background);
    expect(app.theme!.colorScheme.primary, NubeRushColors.primary);
  });
}
