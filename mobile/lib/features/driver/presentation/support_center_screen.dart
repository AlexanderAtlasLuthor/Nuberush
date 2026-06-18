// NubeRush Driver — Support center (Dr.1.5.J).
//
// STATIC / LOCAL-ONLY. Lists the kinds of issues a driver may have and explains
// that in-app live ticketing is not implemented in Dr.1.5 — drivers should use
// the approved NubeRush operations channel outside the app until backend support
// exists. It submits no ticket, calls no support endpoint, starts no live chat,
// sends no email/SMS, exposes no internal URLs or sensitive config.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class SupportCenterScreen extends StatelessWidget {
  const SupportCenterScreen({super.key});

  static const List<String> _categories = <String>[
    'Active delivery issue',
    'App issue',
    'Account / access issue',
    'Store pickup issue',
    'Customer dropoff issue',
    'Failed delivery / return issue',
  ];

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Support center')),
      body: ListView(
        key: const Key('support-center-screen'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.support_agent_outlined,
                        color: NubeRushColors.primary),
                    const SizedBox(width: NubeRushSpacing.sm),
                    Expanded(
                      child: Text('What do you need help with?',
                          style: Theme.of(context).textTheme.titleMedium),
                    ),
                  ],
                ),
                const SizedBox(height: NubeRushSpacing.md),
                for (final category in _categories)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: NubeRushSpacing.xs),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.label_outline,
                            size: 18, color: NubeRushColors.textSecondary),
                        const SizedBox(width: NubeRushSpacing.sm),
                        Expanded(
                          child: Text(
                            category,
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
          NubeRushCard(
            key: const Key('support-center-availability'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('How to get help right now',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: NubeRushSpacing.sm),
                const Text(
                  'In-app live ticketing and chat are not implemented in this '
                  'version. There is no support backend yet, so this screen '
                  'does not submit anything.',
                  style: TextStyle(color: NubeRushColors.textPrimary),
                ),
                const SizedBox(height: NubeRushSpacing.sm),
                const Text(
                  'Until in-app support exists, use the approved NubeRush '
                  'operations channel outside the app to reach the team. Do '
                  'not share customer details over unsecured channels.',
                  style: TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
                ),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('support-center-back'),
            label: 'Back to safety tools',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }
}
