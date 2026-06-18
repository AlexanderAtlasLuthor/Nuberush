// NubeRush Driver — config-required state (Dr.1.4.C).
//
// Shown when required PUBLIC runtime configuration is missing/invalid. It is a
// safe, branded dead-end: it lists the required variable NAMES so a build can
// be fixed, and shows NO values, NO secrets, NO raw exception, NO stack trace,
// and never mentions service-role keys. It makes no network call.
//
// This is NOT an auth screen — it never collects credentials and has no login.

import 'package:flutter/material.dart';

import '../../../core/config/runtime_config.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class ConfigRequiredScreen extends StatelessWidget {
  const ConfigRequiredScreen({super.key, List<String>? requiredVariables})
      : requiredVariables = requiredVariables ?? kRequiredRuntimeVariables;

  /// Names of the required public variables to display. Names only — values are
  /// never passed here. Defaults to the full required set.
  final List<String> requiredVariables;

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      padding: const EdgeInsets.all(NubeRushSpacing.xl),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Center(child: NubeRushBrandHeader()),
                const SizedBox(height: NubeRushSpacing.xl),
                const NubeRushInlineError(
                  message:
                      'Required public runtime configuration is missing or '
                      'invalid.',
                ),
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Configuration required',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: NubeRushSpacing.sm),
                      Text(
                        'Provide the following public variables via '
                        '--dart-define (or --dart-define-from-file) and '
                        'rebuild:',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: NubeRushSpacing.md),
                      for (final name in requiredVariables)
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: NubeRushSpacing.xs,
                          ),
                          child: Text(
                            '• $name',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
