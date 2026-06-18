// NubeRush Driver — terminal assignment history card (Dr.1.5.K).
//
// Renders ONLY the PII-free summary fields the assignments list already returns:
// a short assignment id, store name/code (when present), order status (when
// present), and the assignment status. It shows NO customer name/phone/address,
// NO coordinates, NO DOB/ID/proof/signature/photo, and NO earnings/tips/
// payouts/taxes. An optional read-only "View details" CTA reuses the existing
// assignment detail screen via the injected callback.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';

class HistoryAssignmentCard extends StatelessWidget {
  const HistoryAssignmentCard({
    super.key,
    required this.assignment,
    this.onOpen,
  });

  final DriverAssignmentSummary assignment;

  /// Optional read-only detail navigation (wired by the app shell). When null,
  /// the card is a non-tappable summary.
  final VoidCallback? onOpen;

  String get _shortId {
    final id = assignment.id;
    return id.length <= 8 ? id : '${id.substring(0, 8)}…';
  }

  @override
  Widget build(BuildContext context) {
    final store = assignment.storeName;
    final orderStatus = assignment.orderStatus;
    return NubeRushCard(
      key: Key('history-card-${assignment.id}'),
      onTap: onOpen,
      child: Row(
        children: [
          const Icon(Icons.receipt_long_outlined,
              color: NubeRushColors.primary),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  store == null || store.isEmpty
                      ? 'Assignment $_shortId'
                      : store,
                  style: const TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Assignment: $_shortId',
                  style: const TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
                ),
                Text(
                  'Status: ${assignment.status}',
                  style: const TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
                ),
                if (orderStatus != null && orderStatus.isNotEmpty)
                  Text(
                    'Order: $orderStatus',
                    style: const TextStyle(
                        color: NubeRushColors.textSecondary, fontSize: 13),
                  ),
              ],
            ),
          ),
          if (onOpen != null)
            const Icon(Icons.chevron_right,
                color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }
}
