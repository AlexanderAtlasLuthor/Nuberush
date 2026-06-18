// NubeRush Driver — next action panel (Dr.1.5.E).
//
// Display-only guidance that derives the suggested next step from the SAME
// display-only availability maps that gate the action buttons
// (operationalActionsFor / complianceActionsFor). It unlocks nothing the
// backend doesn't already allow and duplicates no backend rule — it only
// points the driver at the action group below. The backend remains the
// authority; an unknown state falls through to the safe no-action copy.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';

class NextActionPanel extends StatelessWidget {
  const NextActionPanel({
    super.key,
    required this.operationalActions,
    required this.complianceActions,
  });

  final List<DriverOperationalAction> operationalActions;
  final List<DriverComplianceAction> complianceActions;

  /// The suggested next-step label, or null when no action is available.
  String? get _suggestion {
    if (operationalActions.isNotEmpty) return operationalActions.first.label;
    if (complianceActions.isNotEmpty) return complianceActions.first.label;
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final suggestion = _suggestion;
    return NubeRushCard(
      key: const Key('next-action-panel'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Next step', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          if (suggestion != null) ...[
            Text(
              key: const Key('next-action-suggestion'),
              'Suggested: $suggestion',
              style: const TextStyle(
                color: NubeRushColors.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: NubeRushSpacing.xs),
            const Text(
              'Use the action below to continue.',
              style: TextStyle(color: NubeRushColors.textSecondary,
                  fontSize: 13),
            ),
          ] else ...[
            const Text(
              key: Key('next-action-none'),
              'No driver action available right now.',
              style: TextStyle(color: NubeRushColors.textPrimary),
            ),
            const SizedBox(height: NubeRushSpacing.xs),
            const Text(
              'Refresh to check the latest delivery state.',
              style: TextStyle(color: NubeRushColors.textSecondary,
                  fontSize: 13),
            ),
          ],
        ],
      ),
    );
  }
}
