// NubeRush Driver — Emergency help guidance (Dr.1.5.J).
//
// STATIC / LOCAL-ONLY. Informational emergency guidance. It auto-dials nothing,
// uses no phone/SMS API, no device location, no maps, sends no alerts, contacts
// no support backend, and never claims NubeRush is dispatching emergency help
// from the app. It only renders safe copy and a back action.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class EmergencyHelpScreen extends StatelessWidget {
  const EmergencyHelpScreen({super.key});

  static const List<String> _guidance = <String>[
    'Your personal safety comes first. If you are in danger, get to a safe '
        'place before doing anything else.',
    'In an urgent emergency, contact your local emergency services directly '
        'using your phone’s dialer.',
    'Follow local laws and NubeRush policy at all times.',
    'NubeRush does not dispatch emergency services from this app. This screen '
        'is guidance only.',
    'Once you are safe, you can report a delivery incident from the support '
        'tools for NubeRush operations to review.',
  ];

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Emergency help')),
      body: ListView(
        key: const Key('emergency-help-screen'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.emergency_outlined,
                        color: NubeRushColors.danger),
                    const SizedBox(width: NubeRushSpacing.sm),
                    Expanded(
                      child: Text('In an emergency',
                          style: Theme.of(context).textTheme.titleMedium),
                    ),
                  ],
                ),
                const SizedBox(height: NubeRushSpacing.md),
                for (final line in _guidance)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: NubeRushSpacing.xs),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ',
                            style:
                                TextStyle(color: NubeRushColors.textSecondary)),
                        Expanded(
                          child: Text(
                            line,
                            style: const TextStyle(
                                color: NubeRushColors.textPrimary),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('emergency-help-back'),
            label: 'Back to safety tools',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }
}
