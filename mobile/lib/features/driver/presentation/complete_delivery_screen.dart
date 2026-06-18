// NubeRush Driver — dedicated complete-delivery screen (Dr.1.5.G).
//
// A completion confirmation surface. Completion is BACKEND-GATED: the existing
// bodyless `complete` action is submitted and the backend decides whether the
// delivery can be completed (it verifies the prior compliance gates). It sets
// no Order.status locally, touches no inventory, calls no /orders//inventory,
// and fakes no success — on success it leaves the screen only after the
// controller has re-read authoritative state.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import 'assignment_detail_controller.dart';
import 'driver_compliance_action.dart';

class CompleteDeliveryScreen extends StatefulWidget {
  const CompleteDeliveryScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<CompleteDeliveryScreen> createState() => _CompleteDeliveryScreenState();
}

class _CompleteDeliveryScreenState extends State<CompleteDeliveryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.clearActionError();
    });
  }

  Future<void> _submit() async {
    await widget.controller.completeDelivery();
    if (!mounted) return;
    if (!widget.controller.state.hasActionError) {
      Navigator.of(context).maybePop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Complete delivery')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final detail = state.detail;
          final running = state.runningComplianceAction ==
              DriverComplianceAction.completeDelivery;
          final inFlight = state.isActionInFlight;
          return ListView(
            key: const Key('complete-delivery-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Complete this delivery',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'NubeRush verifies the compliance gates and decides '
                      'whether this delivery can be completed.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                    if (detail != null) ...[
                      const SizedBox(height: NubeRushSpacing.md),
                      _line('Assignment', detail.status),
                      if (detail.order != null)
                        _line('Order status', detail.order!.status),
                      if (state.deliveryState != null)
                        _line('Current state', state.deliveryState!.state),
                    ],
                  ],
                ),
              ),
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushInlineError(
                  key: const Key('dropoff-complete-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('dropoff-complete-submit'),
                label: 'Complete delivery',
                isLoading: running,
                onPressed: inFlight ? null : _submit,
              ),
            ],
          );
        },
      ),
    );
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
