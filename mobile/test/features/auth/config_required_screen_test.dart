// NubeRush Driver — ConfigRequiredScreen + app gating tests (Dr.1.4.C).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/app/app_bootstrap.dart';
import 'package:nuberush_driver/core/config/runtime_config.dart';
import 'package:nuberush_driver/core/theme/nuberush_colors.dart';
import 'package:nuberush_driver/features/auth/presentation/config_required_screen.dart';

void main() {
  group('ConfigRequiredScreen', () {
    testWidgets('lists the required variable names', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: ConfigRequiredScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Configuration required'), findsOneWidget);
      for (final name in kRequiredRuntimeVariables) {
        expect(find.textContaining(name), findsOneWidget);
      }
    });

    testWidgets('renders a safe message and no secret values', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: ConfigRequiredScreen()));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('missing or invalid'),
        findsOneWidget,
      );
      // No leaked values / secrets / stack traces.
      expect(find.textContaining('anon-key'), findsNothing);
      expect(find.textContaining('service'), findsNothing);
      expect(find.textContaining('Exception'), findsNothing);
      expect(find.textContaining('#0'), findsNothing);
    });
  });

  group('NubeRushDriverApp bootstrap gating', () {
    testWidgets('config failure renders ConfigRequiredScreen', (tester) async {
      await tester.pumpWidget(
        const NubeRushDriverApp(
          bootstrap: AppBootstrapConfigFailure(kRequiredRuntimeVariables),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(ConfigRequiredScreen), findsOneWidget);
      expect(find.text('Configuration required'), findsOneWidget);
    });

    testWidgets('ready bootstrap renders the Driver Home path (no login)',
        (tester) async {
      final config = RuntimeConfig.fromValues(
        apiBaseUrl: 'https://api.nuberush.test',
        supabaseUrl: 'https://project.supabase.test',
        supabaseAnonKey: 'public-anon-key-value',
      );

      await tester.pumpWidget(
        NubeRushDriverApp(bootstrap: AppBootstrapReady(config)),
      );
      await tester.pump();

      // The Driver Home path renders (not the config screen), and there is no
      // login surface in this subphase.
      expect(find.byType(ConfigRequiredScreen), findsNothing);
      expect(find.text('NubeRush Driver'), findsWidgets);
    });

    testWidgets('root still uses the NubeRush dark theme', (tester) async {
      await tester.pumpWidget(
        const NubeRushDriverApp(
          bootstrap: AppBootstrapConfigFailure(kRequiredRuntimeVariables),
        ),
      );
      await tester.pump();

      final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(app.theme!.brightness, Brightness.dark);
      expect(app.theme!.scaffoldBackgroundColor, NubeRushColors.background);
      expect(app.theme!.colorScheme.primary, NubeRushColors.primary);
    });
  });
}
