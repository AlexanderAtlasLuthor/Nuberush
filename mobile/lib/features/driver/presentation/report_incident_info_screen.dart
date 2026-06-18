// NubeRush Driver — Report delivery incident guidance (Dr.1.5.J).
//
// STATIC / LOCAL-ONLY. Explains common delivery incident categories and points
// the driver at the EXISTING in-app delivery actions where applicable (report
// failed delivery, return to store, wait for store confirmation). It submits no
// incident, calls no fail / return-to-store / support endpoint automatically,
// never cancels an order, releases inventory, confirms a return, or touches
// /orders/* or /inventory/*. In-app incident submission is future work.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class ReportIncidentInfoScreen extends StatelessWidget {
  const ReportIncidentInfoScreen({super.key});

  static const List<String> _categories = <String>[
    'Safety concern',
    'Unable to verify age (21+)',
    'Customer unavailable',
    'Store pickup issue',
    'Damaged or unsealed order concern',
    'Return needed',
  ];

  static const List<String> _guidance = <String>[
    'When a delivery can’t be completed safely, use the in-app delivery actions '
        'on the active delivery: report failed delivery, then return to store '
        'if required.',
    'After returning, wait for the store / NubeRush to complete the final '
        'return confirmation — that step is not done from this app.',
    'Do not include customer personal information in unsecured channels.',
  ];

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Report a delivery incident')),
      body: ListView(
        key: const Key('report-incident-info-screen'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Common incident types',
                    style: Theme.of(context).textTheme.titleMedium),
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
                          child: Text(category,
                              style: const TextStyle(
                                  color: NubeRushColors.textPrimary)),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushCard(
            key: const Key('report-incident-guidance'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('What to do',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: NubeRushSpacing.sm),
                const Text(
                  'In-app incident submission is future work. This screen does '
                  'not submit anything or take action on your delivery.',
                  style: TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
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
                          child: Text(line,
                              style: const TextStyle(
                                  color: NubeRushColors.textPrimary)),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('report-incident-back'),
            label: 'Back to safety tools',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }
}
