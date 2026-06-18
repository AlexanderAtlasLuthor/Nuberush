// NubeRush Driver — active delivery summary card (Dr.1.5.E).
//
// Mission-style header + the PII-free assignment/order/store summary the backend
// already returns. It DISPLAYS only existing fields (lifecycle status, delivery
// operational state, store name/code, order status, and the timestamps present
// on the read models). No customer identity, address, coordinates, phone, or
// invented data. The raw backend `status`/`state` strings are shown verbatim.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_radii.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import '../domain/driver_delivery_state.dart';

class ActiveDeliverySummaryCard extends StatelessWidget {
  const ActiveDeliverySummaryCard({
    super.key,
    required this.detail,
    this.deliveryState,
  });

  final DriverAssignmentDetail detail;
  final DriverDeliveryState? deliveryState;

  @override
  Widget build(BuildContext context) {
    final store = detail.store;
    final order = detail.order;
    return NubeRushCard(
      key: const Key('active-delivery-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.local_shipping, color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Expanded(
                child: Text(
                  'Active delivery',
                  style: const TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                  ),
                ),
              ),
              _StatusChip(label: detail.status),
            ],
          ),
          const SizedBox(height: NubeRushSpacing.md),
          // Preserve the exact backend-reported strings (display-only).
          Text('Status: ${detail.status}',
              style: const TextStyle(color: NubeRushColors.textPrimary)),
          if (deliveryState != null)
            Text('State: ${deliveryState!.state}',
                style: const TextStyle(color: NubeRushColors.textPrimary)),
          const SizedBox(height: NubeRushSpacing.sm),
          if (store != null)
            _line('Store', _storeLabel(store)),
          if (order != null) _line('Order status', order.status),
          ..._timestamps(),
        ],
      ),
    );
  }

  String _storeLabel(DriverAssignmentStore store) {
    final code = store.code.trim();
    return code.isEmpty ? store.name : '${store.name} ($code)';
  }

  List<Widget> _timestamps() {
    final order = detail.order;
    final rows = <Widget>[];
    void add(String label, DateTime? dt) {
      if (dt != null) rows.add(_line(label, _fmt(dt)));
    }

    add('Accepted', detail.acceptedAt ?? order?.acceptedAt);
    add('Delivered', order?.deliveredAt);
    add('Returned', order?.returnedAt);
    add('Canceled', detail.canceledAt ?? order?.canceledAt);
    add('Completed', detail.completedAt);
    return rows;
  }

  Widget _line(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
        child: Row(
          children: [
            Text('$label: ',
                style: const TextStyle(color: NubeRushColors.textSecondary)),
            Expanded(
              child: Text(value,
                  style: const TextStyle(color: NubeRushColors.textPrimary)),
            ),
          ],
        ),
      );

  /// Compact, locale-free timestamp: yyyy-MM-dd HH:mm (local).
  static String _fmt(DateTime dt) {
    final l = dt.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${l.year}-${two(l.month)}-${two(l.day)} '
        '${two(l.hour)}:${two(l.minute)}';
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.sm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: NubeRushColors.primary.withValues(alpha: 0.14),
        borderRadius: NubeRushRadii.borderSm,
        border: Border.all(color: NubeRushColors.primary),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: NubeRushColors.primary,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
