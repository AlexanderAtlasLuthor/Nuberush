// NubeRush Driver — Return-required explanation surface (Dr.1.5.H).
//
// Shown after a failed delivery: it explains that the order could not be
// delivered and may need to be returned to the store, that returning is a
// driver step, and that the STORE / NubeRush completes the final confirmation
// (the backend owns `confirm-driver-return`; mobile never calls it). It shows a
// safe, PII-free assignment / store / order / current-state summary and static
// instructions, and routes to the dedicated ReturnToStoreScreen when the
// existing return-to-store action is available.
//
// It calls NO action itself, uses NO maps / navigation / coordinates, displays
// NO fake store address, creates NO support ticket, and never cancels the order,
// releases inventory, or confirms the return.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';
import 'return_to_store_screen.dart';

class ReturnRequiredScreen extends StatefulWidget {
  const ReturnRequiredScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<ReturnRequiredScreen> createState() => _ReturnRequiredScreenState();
}

class _ReturnRequiredScreenState extends State<ReturnRequiredScreen> {
  @override
  void initState() {
    super.initState();
    if (widget.controller.state.status == AssignmentDetailStatus.initial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        widget.controller.load();
      });
    }
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

  void _openReturnToStore(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ReturnToStoreScreen(controller: widget.controller),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Return required')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final available = _returnAvailable(state);
          return ListView(
            key: const Key('return-required-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.assignment_return_outlined,
                            color: NubeRushColors.primary),
                        const SizedBox(width: NubeRushSpacing.sm),
                        Expanded(
                          child: Text('This order needs to go back',
                              style: Theme.of(context).textTheme.titleMedium),
                        ),
                      ],
                    ),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'This delivery could not be completed, so the order may '
                      'need to be returned to the store. Returning the order is '
                      'a driver step. NubeRush / the store completes the final '
                      'return confirmation — you do not cancel the order or '
                      'release inventory from the app.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: NubeRushSpacing.lg),
              _summaryCard(context, state),
              const SizedBox(height: NubeRushSpacing.lg),
              _instructionsCard(context),
              if (!available) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                const Text(
                  key: Key('return-required-unavailable'),
                  'Return to store isn’t available at the current state. '
                  'Refresh the active delivery to check the latest state.',
                  style: TextStyle(color: NubeRushColors.textSecondary),
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('return-required-continue'),
                label: 'Continue to return to store',
                onPressed:
                    available ? () => _openReturnToStore(context) : null,
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
      key: const Key('return-required-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Summary', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.md),
          if (store != null) _line('Store', _storeLabel(store)),
          if (detail != null) _line('Assignment', detail.status),
          if (order != null) _line('Order status', order.status),
          if (deliveryState != null) _line('Current state', deliveryState.state),
        ],
      ),
    );
  }

  Widget _instructionsCard(BuildContext context) {
    return NubeRushCard(
      key: const Key('return-required-instructions'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('What to do', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            '1. Keep the order secure.\n'
            '2. Take it back to the same store.\n'
            '3. Start the return and confirm arrival at the store.\n'
            '4. Store staff complete the final return confirmation.',
            style: TextStyle(color: NubeRushColors.textPrimary),
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
