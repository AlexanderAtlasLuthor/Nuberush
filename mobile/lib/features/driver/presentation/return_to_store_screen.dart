// NubeRush Driver — Return-to-store action surface (Dr.1.5.H).
//
// A dedicated surface for the driver's return-to-store custody step. It uses
// ONLY the existing `return-to-store` compliance action and only when the
// backend currently offers it. The SAME action carries two backend semantics:
// it STARTS the return while the delivery is `delivery_failed`, and marks
// ARRIVAL back at the store while `returning_to_store`. The screen derives which
// from the backend-reported delivery state — it computes no transition locally.
//
// It NEVER calls the store-side `confirm-driver-return`, cancels the order,
// releases inventory, calls /orders/* or /inventory/*, uses maps / navigation /
// url_launcher / location, or fakes return completion. On success the controller
// re-reads authoritative state (safe GET); on failure a non-destructive inline
// error is shown and nothing navigates away.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import '../domain/driver_assignment.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';

class ReturnToStoreScreen extends StatefulWidget {
  const ReturnToStoreScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<ReturnToStoreScreen> createState() => _ReturnToStoreScreenState();
}

class _ReturnToStoreScreenState extends State<ReturnToStoreScreen> {
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final c = widget.controller;
      // Reached from a loaded flow normally; load defensively if opened cold.
      if (c.state.status == AssignmentDetailStatus.initial) {
        c.load();
      } else {
        c.clearActionError();
      }
    });
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  bool _returnAvailable(AssignmentDetailState state) {
    final detail = state.detail;
    if (detail == null) return false;
    final actions = complianceActionsFor(
      assignmentStatus: detail.status,
      deliveryState: state.deliveryState?.state,
    );
    return actions.contains(DriverComplianceAction.returnToStore);
  }

  /// start while `delivery_failed`; arrive while `returning_to_store`. Mirrors
  /// the existing assignment-detail mapping — no local transition computed.
  ReturnAction _returnActionFor(AssignmentDetailState state) =>
      state.deliveryState?.state == 'returning_to_store'
          ? ReturnAction.arrive
          : ReturnAction.start;

  Future<void> _submit(ReturnAction action) async {
    final isStart = action == ReturnAction.start;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isStart ? 'Start return to store' : 'Confirm arrival'),
        content: Text(
          isStart
              ? 'Start returning this order to the store? The store / NubeRush '
                  'completes the final return confirmation — you are not '
                  'cancelling the order or releasing inventory.'
              : 'Confirm you are back at the store with this order? The store / '
                  'NubeRush completes the final return confirmation.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('return-to-store-confirm'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(isStart ? 'Start return' : 'Confirm arrival'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final note = _note.text.trim();
    await widget.controller.returnToStore(
      ReturnToStoreRequest(action: action, note: note.isEmpty ? null : note),
    );
    if (!mounted) return;
    // Success (re-read, no inline error) or auth-expired -> leave the screen.
    if (!widget.controller.state.hasActionError) {
      Navigator.of(context).maybePop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Return to store')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final running = state.runningComplianceAction ==
              DriverComplianceAction.returnToStore;
          final inFlight = state.isActionInFlight;
          final available = _returnAvailable(state);
          final action = _returnActionFor(state);
          final isStart = action == ReturnAction.start;
          return ListView(
            key: const Key('return-to-store-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              _summaryCard(context, state, isStart),
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isStart
                          ? 'Start the return'
                          : 'Confirm arrival at the store',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: NubeRushSpacing.sm),
                    Text(
                      isStart
                          ? 'You are taking this order back to the store. This '
                              'starts the return leg — it does not complete the '
                              'return.'
                          : 'You are confirming you are back at the store with '
                              'this order. The store / NubeRush completes the '
                              'final return confirmation.',
                      style: const TextStyle(color: NubeRushColors.textPrimary),
                    ),
                    TextField(
                      key: const Key('return-to-store-note'),
                      controller: _note,
                      enabled: !inFlight,
                      maxLength: 500,
                      decoration: const InputDecoration(
                          labelText: 'Note (optional)'),
                    ),
                  ],
                ),
              ),
              if (!available) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                const Text(
                  key: Key('return-to-store-unavailable'),
                  'Return to store isn’t available at the current state.',
                  style: TextStyle(color: NubeRushColors.textSecondary),
                ),
              ],
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushInlineError(
                  key: const Key('return-to-store-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('return-to-store-submit'),
                label: isStart ? 'Start return to store' : 'Confirm arrival',
                isLoading: running,
                onPressed:
                    (available && !inFlight) ? () => _submit(action) : null,
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _summaryCard(
    BuildContext context,
    AssignmentDetailState state,
    bool isStart,
  ) {
    final detail = state.detail;
    final store = detail?.store;
    final order = detail?.order;
    final deliveryState = state.deliveryState;
    return NubeRushCard(
      key: const Key('return-to-store-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.store_mall_directory_outlined,
                  color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Text('Return to store',
                  style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
          const SizedBox(height: NubeRushSpacing.md),
          if (store != null) _line('Store', _storeLabel(store)),
          if (detail != null) _line('Assignment', detail.status),
          if (order != null) _line('Order status', order.status),
          if (deliveryState != null) _line('Current state', deliveryState.state),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            'Final return confirmation is store-side / backend-owned.',
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
