// NubeRush Driver — compliance status card (Dr.1.5.E).
//
// Shows which compliance steps are AVAILABLE right now, derived from the same
// display-only `complianceActionsFor` map that gates the compliance buttons. It
// makes NO completion claims: it never states age was verified or proof exists,
// shows no DOB/ID/photo/signature, and computes no legal compliance. Backend
// state/data remain the only authority — "Available" means the backend
// currently permits the action, nothing more.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_radii.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import 'driver_compliance_action.dart';

class ComplianceStatusCard extends StatelessWidget {
  const ComplianceStatusCard({super.key, required this.complianceActions});

  final List<DriverComplianceAction> complianceActions;

  bool _has(DriverComplianceAction a) => complianceActions.contains(a);

  @override
  Widget build(BuildContext context) {
    final failOrReturn = _has(DriverComplianceAction.reportFailedDelivery) ||
        _has(DriverComplianceAction.returnToStore);
    return NubeRushCard(
      key: const Key('compliance-status-card'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Compliance status',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.xs),
          const Text(
            'The backend unlocks each step and verifies the outcome.',
            style: TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: NubeRushSpacing.md),
          _row('Age verification', _has(DriverComplianceAction.verifyAge)),
          _row('Proof of delivery', _has(DriverComplianceAction.submitProof)),
          _row('Complete delivery',
              _has(DriverComplianceAction.completeDelivery)),
          _row('Report issue / return', failOrReturn),
        ],
      ),
    );
  }

  Widget _row(String label, bool available) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
      child: Row(
        children: [
          Expanded(
            child: Text(label,
                style: const TextStyle(color: NubeRushColors.textPrimary)),
          ),
          _AvailabilityChip(available: available),
        ],
      ),
    );
  }
}

class _AvailabilityChip extends StatelessWidget {
  const _AvailabilityChip({required this.available});

  final bool available;

  @override
  Widget build(BuildContext context) {
    final color =
        available ? NubeRushColors.success : NubeRushColors.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.sm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: NubeRushRadii.borderSm,
        border: Border.all(color: color),
      ),
      child: Text(
        available ? 'Available now' : 'Locked',
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}
