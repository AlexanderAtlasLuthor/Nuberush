// NubeRush Driver — Failed Delivery reason surface (Dr.1.5.H).
//
// The canonical failed-delivery reason screen. It uses ONLY the existing `fail`
// compliance action (DriverFailDeliveryRequest) and only when the backend
// currently offers it. A structured reason is REQUIRED; an optional safe note
// is supported by the existing payload. Confirmation precedes submission.
//
// It NEVER cancels the order locally, releases inventory, starts return-to-store
// automatically, calls /orders/* or /inventory/*, invents customer details, or
// submits photos/signatures/PINs. On success the controller re-reads the
// authoritative detail + delivery-state (safe GET) and the screen leaves; on
// failure a non-destructive inline error is shown and nothing navigates away.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';

class FailedDeliveryReasonScreen extends StatefulWidget {
  const FailedDeliveryReasonScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<FailedDeliveryReasonScreen> createState() =>
      _FailedDeliveryReasonScreenState();
}

class _FailedDeliveryReasonScreenState
    extends State<FailedDeliveryReasonScreen> {
  // Required: no reason is pre-selected so the driver must choose one.
  FailureReason? _reason;
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

  bool _failAvailable(AssignmentDetailState state) {
    final detail = state.detail;
    if (detail == null) return false;
    final actions = complianceActionsFor(
      assignmentStatus: detail.status,
      deliveryState: state.deliveryState?.state,
    );
    return actions.contains(DriverComplianceAction.reportFailedDelivery);
  }

  Future<void> _submit() async {
    final reason = _reason;
    if (reason == null) return; // required
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Report failed delivery'),
        content: const Text(
          'Submit this delivery as failed? The order cannot be completed. '
          'NubeRush records the outcome and decides what happens next — you '
          'do not cancel the order or release inventory from here.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('failed-delivery-confirm'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Report failed'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final note = _note.text.trim();
    await widget.controller.failDelivery(
      FailRequest(reasonCode: reason, note: note.isEmpty ? null : note),
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
      appBar: AppBar(title: const Text('Failed delivery')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final running = state.runningComplianceAction ==
              DriverComplianceAction.reportFailedDelivery;
          final inFlight = state.isActionInFlight;
          final available = _failAvailable(state);
          return ListView(
            key: const Key('failed-delivery-reason-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Why did this delivery fail?',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'Choose the reason this delivery cannot be completed. '
                      'Do not mark a delivery complete when you cannot hand it '
                      'over safely. NubeRush records and verifies the outcome.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                    const SizedBox(height: NubeRushSpacing.md),
                    DropdownButton<FailureReason>(
                      key: const Key('failed-delivery-reason'),
                      isExpanded: true,
                      value: _reason,
                      hint: const Text('Select a reason'),
                      items: [
                        for (final r in FailureReason.values)
                          DropdownMenuItem(value: r, child: Text(r.label)),
                      ],
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _reason = v),
                    ),
                    TextField(
                      key: const Key('failed-delivery-note'),
                      controller: _note,
                      enabled: !inFlight,
                      maxLength: 500,
                      decoration: const InputDecoration(
                          labelText: 'Note (optional)'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: NubeRushSpacing.md),
              const Text(
                'After a failed delivery the order may need to be returned to '
                'the store. Returning is a separate driver step, and final '
                'confirmation is completed by the store / NubeRush.',
                style:
                    TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
              ),
              if (!available) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                const Text(
                  key: Key('failed-delivery-unavailable'),
                  'Reporting a failed delivery isn’t available at the current '
                  'state.',
                  style: TextStyle(color: NubeRushColors.textSecondary),
                ),
              ],
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushInlineError(
                  key: const Key('failed-delivery-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('failed-delivery-submit'),
                label: 'Report failed delivery',
                isLoading: running,
                // Disabled until a reason is chosen and while any action runs
                // or the backend doesn't offer fail.
                onPressed: (available && _reason != null && !inFlight)
                    ? _submit
                    : null,
              ),
            ],
          );
        },
      ),
    );
  }
}
