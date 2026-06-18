// NubeRush Driver — Failed Delivery / Return hub (Dr.1.5.H).
//
// A dedicated hub for the FAILED-DELIVERY / RETURN path. It reuses the existing
// AssignmentDetailController (same loaded detail + delivery-state, same
// compliance availability) and routes to the dedicated step screens. It adds no
// endpoint, no new controller, and no local lifecycle / inventory mutation. The
// backend remains the authority: each step is offered only when the existing
// availability map / backend-loaded state permits it, and failures stay
// non-destructive.
//
// It NEVER performs store-side return confirmation (`confirm-driver-return`),
// cancels the order, releases inventory, calls /orders/* or /inventory/*, or
// uses maps / navigation / coordinates.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'driver_compliance_action.dart';
import 'failed_delivery_reason_screen.dart';
import 'failed_return_flow.dart';
import 'return_pending_confirmation_screen.dart';
import 'return_required_screen.dart';

class FailedReturnFlowScreen extends StatefulWidget {
  const FailedReturnFlowScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<FailedReturnFlowScreen> createState() => _FailedReturnFlowScreenState();
}

class _FailedReturnFlowScreenState extends State<FailedReturnFlowScreen> {
  @override
  void initState() {
    super.initState();
    if (widget.controller.state.status == AssignmentDetailStatus.initial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        widget.controller.load();
      });
    }
  }

  void _open(Widget Function() build) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => build()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Failed delivery / Return')),
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
          key: Key('failed-return-loading'),
          child: NubeRushLoadingState(),
        );
      case AssignmentDetailStatus.unauthenticated:
        return const _Message(
          key: Key('failed-return-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case AssignmentDetailStatus.offline:
        return _Message(
          key: const Key('failed-return-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case AssignmentDetailStatus.error:
        return _Message(
          key: const Key('failed-return-error'),
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
    final compliance = detail == null
        ? const <DriverComplianceAction>[]
        : complianceActionsFor(
            assignmentStatus: detail.status,
            deliveryState: deliveryState?.state,
          );
    final stage = failedReturnStage(
      compliance: compliance,
      detail: detail,
      deliveryState: deliveryState,
    );

    return SingleChildScrollView(
      key: const Key('failed-return-loaded'),
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
          ..._stageSection(context, stage),
        ],
      ),
    );
  }

  List<Widget> _stageSection(BuildContext context, FailedReturnStage stage) {
    switch (stage) {
      case FailedReturnStage.reportFail:
        return [
          _StepEntry(
            key: const Key('failed-return-step-fail'),
            icon: Icons.report_gmailerrorred_outlined,
            title: 'Report failed delivery',
            subtitle: "Use when the order can't be delivered safely.",
            onTap: () => _open(() =>
                FailedDeliveryReasonScreen(controller: widget.controller)),
          ),
        ];
      case FailedReturnStage.returnToStore:
        return [
          _StepEntry(
            key: const Key('failed-return-step-return'),
            icon: Icons.assignment_return_outlined,
            title: 'Return order to store',
            subtitle: 'This order needs to go back to the store.',
            onTap: () => _open(
                () => ReturnRequiredScreen(controller: widget.controller)),
          ),
        ];
      case FailedReturnStage.returnPending:
        return [
          _StepEntry(
            key: const Key('failed-return-step-pending'),
            icon: Icons.inventory_2_outlined,
            title: 'Return pending confirmation',
            subtitle: 'Awaiting store / NubeRush confirmation.',
            onTap: () => _open(() =>
                ReturnPendingConfirmationScreen(controller: widget.controller)),
          ),
        ];
      case FailedReturnStage.notRelevant:
        return [_notActive(context, widget.controller.state)];
    }
  }

  Widget _summaryCard(BuildContext context, AssignmentDetailState state) {
    final detail = state.detail!;
    final store = detail.store;
    final order = detail.order;
    final deliveryState = state.deliveryState;
    return NubeRushCard(
      key: const Key('failed-return-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.error_outline, color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Text('Failed delivery / Return',
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
            'The order cannot be completed. Returning is a driver step; final '
            'confirmation is store-side / backend-owned.',
            style:
                TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _notActive(BuildContext context, AssignmentDetailState state) {
    final deliveryState = state.deliveryState?.state;
    return NubeRushCard(
      key: const Key('failed-return-not-active'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('No failed-delivery or return step',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          Text(
            deliveryState == null
                ? 'There is no failed-delivery or return action available '
                    'right now.'
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
      key: const Key('failed-return-action-error'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NubeRushInlineError(message: state.actionErrorMessage ?? ''),
        const SizedBox(height: NubeRushSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              key: const Key('failed-return-action-error-dismiss'),
              onPressed: inFlight ? null : widget.controller.clearActionError,
              child: const Text('Dismiss'),
            ),
            const SizedBox(width: NubeRushSpacing.sm),
            FilledButton(
              key: const Key('failed-return-action-error-reload'),
              onPressed: inFlight ? null : () => widget.controller.reload(),
              child: const Text('Reload'),
            ),
          ],
        ),
      ],
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

class _StepEntry extends StatelessWidget {
  const _StepEntry({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Padding(
      padding: const EdgeInsets.only(bottom: NubeRushSpacing.md),
      child: NubeRushCard(
        onTap: onTap,
        child: Row(
          children: [
            Icon(icon,
                color:
                    enabled ? NubeRushColors.primary : NubeRushColors.disabled),
            const SizedBox(width: NubeRushSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(
                        color: NubeRushColors.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      )),
                  const SizedBox(height: 2),
                  Text(subtitle,
                      style: const TextStyle(
                          color: NubeRushColors.textSecondary, fontSize: 13)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right,
                color: NubeRushColors.textSecondary),
          ],
        ),
      ),
    );
  }
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
                key: const Key('failed-return-retry'),
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
