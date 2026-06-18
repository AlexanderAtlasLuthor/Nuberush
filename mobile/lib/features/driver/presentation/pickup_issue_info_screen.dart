// NubeRush Driver — pickup issue info (Dr.1.5.F).
//
// INFORMATIONAL ONLY. Static guidance for when a store pickup can't be
// completed. It submits nothing: no support ticket, no backend issue payload,
// no fail/return endpoint (that is Dr.1.5.H). It only explains the approved
// process and lets the driver return to the active delivery.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class PickupIssueInfoScreen extends StatelessWidget {
  const PickupIssueInfoScreen({super.key});

  static const List<String> _guidance = <String>[
    'Ask store staff to confirm the order is ready for NubeRush.',
    "Don't mark pickup until the order is physically in your possession.",
    'Keep the order sealed and follow restricted-product handling rules.',
    "If the order can't be picked up, contact NubeRush / store operations "
        'through the approved process.',
  ];

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Pickup issue')),
      body: ListView(
        key: const Key('pickup-issue-info'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.info_outline,
                        color: NubeRushColors.primary),
                    const SizedBox(width: NubeRushSpacing.sm),
                    Text('Having trouble picking up?',
                        style: Theme.of(context).textTheme.titleMedium),
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
            key: const Key('pickup-issue-back'),
            label: 'Back to delivery',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }
}
