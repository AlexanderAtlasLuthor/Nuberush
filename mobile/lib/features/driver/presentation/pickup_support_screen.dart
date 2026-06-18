// NubeRush Driver — Pickup Support Surface (Dr.1.5.F).
//
// A dedicated, operational-assistant view for the STORE PICKUP stage. It reuses
// the existing AssignmentDetailController (same loaded detail + delivery-state)
// and the existing operational actions `arrive-store` and `pickup` — no new
// endpoint, no new controller, no local lifecycle/inventory mutation. The
// backend remains the authority: actions are offered only when the existing
// availability map permits them, and an action failure is non-destructive
// (the loaded surface stays, an inline error is shown, 401 falls through to
// the auth-expired state).
//
// It does NOT call /orders/* or /inventory/*, send a pickup PIN or issue
// payload, invent pickup proof, or implement Dr.1.5.G/.H.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_operational_action.dart';
import 'pickup_checklist.dart';
import 'pickup_issue_info_screen.dart';

class PickupSupportScreen extends StatefulWidget {
  const PickupSupportScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<PickupSupportScreen> createState() => _PickupSupportScreenState();
}

class _PickupSupportScreenState extends State<PickupSupportScreen> {
  bool _checklistReady = false;

  @override
  void initState() {
    super.initState();
    // Self-sufficient when opened directly; a no-op when entered from the
    // already-loaded detail screen (same controller instance).
    if (widget.controller.state.status == AssignmentDetailStatus.initial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        widget.controller.load();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Store pickup')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) => _body(context, widget.controller.state),
      ),
    );
  }

  Widget _body(BuildContext context, AssignmentDetailState state) {
    switch (state.status) {
      case AssignmentDetailStatus.initial:
      case AssignmentDetailStatus.loading:
        return const Center(
          key: Key('pickup-loading'),
          child: NubeRushLoadingState(),
        );
      case AssignmentDetailStatus.unauthenticated:
        return const _Message(
          key: Key('pickup-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case AssignmentDetailStatus.offline:
        return _Message(
          key: const Key('pickup-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case AssignmentDetailStatus.error:
        return _Message(
          key: const Key('pickup-error'),
          icon: Icons.error_outline,
          message: state.errorMessage ?? 'Something went wrong.',
          onRetry: widget.controller.retry,
        );
      case AssignmentDetailStatus.loaded:
        return _loaded(context, state);
    }
  }

  Widget _loaded(BuildContext context, AssignmentDetailState state) {
    final detail = state.detail;
    final deliveryState = state.deliveryState;
    final actions = detail == null
        ? const <DriverOperationalAction>[]
        : operationalActionsFor(
            assignmentStatus: detail.status,
            deliveryState: deliveryState?.state,
          );
    final hasArrive = actions.contains(DriverOperationalAction.arriveStore);
    final hasPickup = actions.contains(DriverOperationalAction.pickup);
    final inFlight = state.isActionInFlight;

    return SingleChildScrollView(
      key: const Key('pickup-loaded'),
      padding: const EdgeInsets.all(NubeRushSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (state.actionErrorMessage != null) ...[
            _actionError(state),
            const SizedBox(height: NubeRushSpacing.lg),
          ],
          if (detail != null) ...[
            _summaryCard(context, state),
            const SizedBox(height: NubeRushSpacing.lg),
          ],
          if (hasArrive)
            _arrivalSection(context, state)
          else if (hasPickup)
            _pickupSection(context, state)
          else
            _notActiveCard(context, deliveryState?.state),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushSecondaryButton(
            key: const Key('pickup-issue-entry'),
            label: 'Report a pickup issue',
            onPressed: inFlight ? null : () => _openIssueInfo(context),
          ),
        ],
      ),
    );
  }

  // --- Sections -------------------------------------------------------- //

  Widget _summaryCard(BuildContext context, AssignmentDetailState state) {
    final detail = state.detail!;
    final store = detail.store;
    final order = detail.order;
    final deliveryState = state.deliveryState;
    return NubeRushCard(
      key: const Key('pickup-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.store_mall_directory_outlined,
                  color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Text('Store pickup',
                  style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
          const SizedBox(height: NubeRushSpacing.md),
          if (store != null) _line('Store', _storeLabel(store)),
          _line('Assignment', detail.status),
          if (order != null) _line('Order status', order.status),
          if (deliveryState != null) _line('Current state', deliveryState.state),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            'Pickup details come from the backend assignment state.',
            style:
                TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _arrivalSection(BuildContext context, AssignmentDetailState state) {
    final running =
        state.runningAction == DriverOperationalAction.arriveStore;
    return NubeRushCard(
      key: const Key('pickup-arrival'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Arrive at the store',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            'Mark arrival once you reach the store so NubeRush knows you are '
            'ready to pick up.',
            style: TextStyle(color: NubeRushColors.textPrimary),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('pickup-arrive-store'),
            label: 'Arrive at store',
            isLoading: running,
            onPressed: state.isActionInFlight
                ? null
                : () => widget.controller
                    .runAction(DriverOperationalAction.arriveStore),
          ),
        ],
      ),
    );
  }

  Widget _pickupSection(BuildContext context, AssignmentDetailState state) {
    final running = state.runningAction == DriverOperationalAction.pickup;
    final canConfirm =
        _checklistReady && !state.isActionInFlight;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        PickupChecklist(
          enabled: !state.isActionInFlight,
          onReadyChanged: (ready) => setState(() => _checklistReady = ready),
        ),
        const SizedBox(height: NubeRushSpacing.lg),
        NubeRushCard(
          key: const Key('pickup-confirm'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Confirm pickup',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: NubeRushSpacing.sm),
              const Text(
                'Marking pickup tells NubeRush you have the sealed order and '
                'are leaving for the customer.',
                style: TextStyle(color: NubeRushColors.textPrimary),
              ),
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('pickup-confirm-pickup'),
                label: 'Confirm pickup',
                isLoading: running,
                onPressed: canConfirm
                    ? () => widget.controller
                        .runAction(DriverOperationalAction.pickup)
                    : null,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _notActiveCard(BuildContext context, String? deliveryState) {
    return NubeRushCard(
      key: const Key('pickup-not-active'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Pickup isn’t the current step',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          Text(
            deliveryState == null
                ? 'There is no pickup action available right now.'
                : 'Current delivery state: $deliveryState.',
            style: const TextStyle(color: NubeRushColors.textPrimary),
          ),
          const SizedBox(height: NubeRushSpacing.xs),
          const Text(
            'Refresh the active delivery to check the latest state.',
            style:
                TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _actionError(AssignmentDetailState state) {
    final inFlight = state.isActionInFlight;
    return Column(
      key: const Key('pickup-action-error'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NubeRushInlineError(message: state.actionErrorMessage ?? ''),
        const SizedBox(height: NubeRushSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              key: const Key('pickup-action-error-dismiss'),
              onPressed: inFlight ? null : widget.controller.clearActionError,
              child: const Text('Dismiss'),
            ),
            const SizedBox(width: NubeRushSpacing.sm),
            FilledButton(
              key: const Key('pickup-action-error-reload'),
              onPressed: inFlight ? null : () => widget.controller.reload(),
              child: const Text('Reload'),
            ),
          ],
        ),
      ],
    );
  }

  // --- Helpers --------------------------------------------------------- //

  void _openIssueInfo(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const PickupIssueInfoScreen(),
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

class _Message extends StatelessWidget {
  const _Message({
    super.key,
    required this.icon,
    required this.message,
    this.onRetry,
  });

  final IconData icon;
  final String message;
  final Future<void> Function()? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(NubeRushSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: NubeRushColors.textSecondary),
            const SizedBox(height: NubeRushSpacing.lg),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: NubeRushSpacing.lg),
              FilledButton(
                key: const Key('pickup-retry'),
                onPressed: () => onRetry!(),
                child: const Text('Retry'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
