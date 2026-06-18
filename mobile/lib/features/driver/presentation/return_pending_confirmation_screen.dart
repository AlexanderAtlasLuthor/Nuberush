// NubeRush Driver — Return pending store confirmation surface (Dr.1.5.H).
//
// Shown once the driver has returned the order to the store (backend-loaded
// `returned_to_store` delivery state, or a `returned` order status /
// `returned_at` timestamp). It tells the driver that the driver-side return is
// done and that the STORE / NubeRush staff must complete the final confirmation
// — the backend owns `confirm-driver-return` and mobile never calls it.
//
// It calls NO action, never cancels the order, releases inventory, or calls
// /orders/* or /inventory/*. It claims no final cancellation / refund — it only
// shows what the backend-loaded status already reports — and offers safe
// navigation back to the active delivery / home.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';

class ReturnPendingConfirmationScreen extends StatefulWidget {
  const ReturnPendingConfirmationScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<ReturnPendingConfirmationScreen> createState() =>
      _ReturnPendingConfirmationScreenState();
}

class _ReturnPendingConfirmationScreenState
    extends State<ReturnPendingConfirmationScreen> {
  @override
  void initState() {
    super.initState();
    if (widget.controller.state.status == AssignmentDetailStatus.initial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        widget.controller.load();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Return pending')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          return ListView(
            key: const Key('return-pending-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.inventory_2_outlined,
                            color: NubeRushColors.primary),
                        const SizedBox(width: NubeRushSpacing.sm),
                        Expanded(
                          child: Text('Returned — awaiting store confirmation',
                              style: Theme.of(context).textTheme.titleMedium),
                        ),
                      ],
                    ),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'You have returned this order to the store. The store / '
                      'NubeRush staff must complete the final return '
                      'confirmation. There is nothing left for you to submit '
                      'here — you do not cancel the order or release inventory.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: NubeRushSpacing.lg),
              _summaryCard(context, state),
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('return-pending-back-active'),
                label: 'Back to active delivery',
                onPressed: () => Navigator.of(context).maybePop(),
              ),
              const SizedBox(height: NubeRushSpacing.sm),
              NubeRushSecondaryButton(
                key: const Key('return-pending-home'),
                label: 'Back to home',
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _summaryCard(BuildContext context, AssignmentDetailState state) {
    final detail = state.detail;
    final store = detail?.store;
    final order = detail?.order;
    final deliveryState = state.deliveryState;
    return NubeRushCard(
      key: const Key('return-pending-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Summary', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.md),
          if (store != null) _line('Store', _storeLabel(store)),
          if (detail != null) _line('Assignment', detail.status),
          if (order != null) _line('Order status', order.status),
          if (deliveryState != null) _line('Current state', deliveryState.state),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            'Final confirmation is store-side / backend-owned.',
            style:
                TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  String _storeLabel(DriverAssignmentStore store) {
    final code = store.code.trim();
    return code.isEmpty ? store.name : '${store.name} (${store.code})';
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
}
