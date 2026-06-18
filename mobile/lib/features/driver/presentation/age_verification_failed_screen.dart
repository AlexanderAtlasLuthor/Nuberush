// NubeRush Driver — failed delivery / can't-verify surface (Dr.1.5.G).
//
// The dropoff failure path. It uses ONLY the existing `fail` compliance action
// (DriverFailDeliveryRequest) when the backend currently allows it. It does NOT
// start or call return-to-store (that is Dr.1.5.H), cancel an order, release
// inventory, or touch /orders//inventory. A confirmation precedes submission.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';

class AgeVerificationFailedScreen extends StatefulWidget {
  const AgeVerificationFailedScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<AgeVerificationFailedScreen> createState() =>
      _AgeVerificationFailedScreenState();
}

class _AgeVerificationFailedScreenState
    extends State<AgeVerificationFailedScreen> {
  FailureReason _reason = FailureReason.customerUnderage;
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.clearActionError();
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
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Report failed delivery'),
        content: const Text(
          "Submit this delivery as failed? Don't complete a delivery you "
          "can't verify. The backend records the outcome.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('dropoff-fail-confirm'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Report failed'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final note = _note.text.trim();
    await widget.controller.failDelivery(
      FailRequest(reasonCode: _reason, note: note.isEmpty ? null : note),
    );
    if (!mounted) return;
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
            key: const Key('age-verification-failed-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Can’t complete this delivery',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'If you cannot verify the recipient or hand over the '
                      'order safely, report the delivery as failed. Do not '
                      'mark it complete.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                    const SizedBox(height: NubeRushSpacing.md),
                    DropdownButton<FailureReason>(
                      key: const Key('dropoff-fail-reason'),
                      isExpanded: true,
                      value: _reason,
                      items: [
                        for (final r in FailureReason.values)
                          DropdownMenuItem(value: r, child: Text(r.label)),
                      ],
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _reason = v ?? _reason),
                    ),
                    TextField(
                      key: const Key('dropoff-fail-note'),
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
                  key: Key('dropoff-fail-unavailable'),
                  'Reporting a failed delivery isn’t available at the current '
                  'state.',
                  style: TextStyle(color: NubeRushColors.textSecondary),
                ),
              ],
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushInlineError(
                  key: const Key('dropoff-fail-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('dropoff-fail-submit'),
                label: 'Report failed delivery',
                isLoading: running,
                onPressed: (available && !inFlight) ? _submit : null,
              ),
            ],
          );
        },
      ),
    );
  }
}
