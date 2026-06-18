// NubeRush Driver — Dropoff / Compliance Support hub (Dr.1.5.G).
//
// A dedicated hub for the CUSTOMER DROPOFF stage. It reuses the existing
// AssignmentDetailController (same loaded detail + delivery-state, same
// compliance/operational actions) and routes to dedicated step screens. It
// adds no endpoint, no new controller, and no local lifecycle/inventory
// mutation. The backend remains the authority: each step is offered only when
// the existing availability map permits it, and failures stay non-destructive.
//
// It does NOT implement return-to-store (Dr.1.5.H), maps/navigation, ID scan,
// photo/signature, customer PIN, or display any customer PII.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'age_verification_failed_screen.dart';
import 'age_verification_screen.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'complete_delivery_screen.dart';
import 'compliance_status_card.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';
import 'proof_of_delivery_screen.dart';

class DropoffSupportScreen extends StatefulWidget {
  const DropoffSupportScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<DropoffSupportScreen> createState() => _DropoffSupportScreenState();
}

class _DropoffSupportScreenState extends State<DropoffSupportScreen> {
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
      appBar: AppBar(title: const Text('Customer dropoff')),
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
          key: Key('dropoff-loading'),
          child: NubeRushLoadingState(),
        );
      case AssignmentDetailStatus.unauthenticated:
        return const _Message(
          key: Key('dropoff-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case AssignmentDetailStatus.offline:
        return _Message(
          key: const Key('dropoff-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case AssignmentDetailStatus.error:
        return _Message(
          key: const Key('dropoff-error'),
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
    final compliance = detail == null
        ? const <DriverComplianceAction>[]
        : complianceActionsFor(
            assignmentStatus: detail.status,
            deliveryState: deliveryState?.state,
          );

    final hasArriveCustomer =
        actions.contains(DriverOperationalAction.arriveCustomer);
    final hasVerify = compliance.contains(DriverComplianceAction.verifyAge);
    final hasProof = compliance.contains(DriverComplianceAction.submitProof);
    final hasComplete =
        compliance.contains(DriverComplianceAction.completeDelivery);
    final hasFail =
        compliance.contains(DriverComplianceAction.reportFailedDelivery);
    final isCompleted = detail?.status == 'completed' ||
        deliveryState?.state == 'delivery_completed';

    return SingleChildScrollView(
      key: const Key('dropoff-loaded'),
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
            ComplianceStatusCard(complianceActions: compliance),
            const SizedBox(height: NubeRushSpacing.lg),
          ],
          if (isCompleted)
            _completedSummary(context, state)
          else if (hasArriveCustomer)
            _arrivalSection(context, state)
          else if (hasVerify || hasProof || hasComplete || hasFail)
            _stepsSection(
              hasVerify: hasVerify,
              hasProof: hasProof,
              hasComplete: hasComplete,
              hasFail: hasFail,
            )
          else
            _notActive(context, deliveryState?.state),
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
      key: const Key('dropoff-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.handshake_outlined,
                  color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Text('Customer dropoff',
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
            'The backend decides whether each compliance step is allowed.',
            style:
                TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _arrivalSection(BuildContext context, AssignmentDetailState state) {
    final running =
        state.runningAction == DriverOperationalAction.arriveCustomer;
    return NubeRushCard(
      key: const Key('dropoff-arrival'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Arrive at the customer',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          const Text(
            'Mark arrival when you reach the customer so you can start the '
            'compliance steps.',
            style: TextStyle(color: NubeRushColors.textPrimary),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('dropoff-arrive-customer'),
            label: 'Arrive at customer',
            isLoading: running,
            onPressed: state.isActionInFlight
                ? null
                : () => widget.controller
                    .runAction(DriverOperationalAction.arriveCustomer),
          ),
        ],
      ),
    );
  }

  Widget _stepsSection({
    required bool hasVerify,
    required bool hasProof,
    required bool hasComplete,
    required bool hasFail,
  }) {
    final inFlight = widget.controller.state.isActionInFlight;
    return Column(
      key: const Key('dropoff-steps'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (hasVerify)
          _StepEntry(
            key: const Key('dropoff-step-verify-age'),
            icon: Icons.verified_user_outlined,
            title: 'Verify age (21+)',
            subtitle: 'Confirm the recipient meets NubeRush policy.',
            onTap: inFlight
                ? null
                : () => _open(() =>
                    AgeVerificationScreen(controller: widget.controller)),
          ),
        if (hasProof)
          _StepEntry(
            key: const Key('dropoff-step-proof'),
            icon: Icons.checklist_rtl,
            title: 'Proof of delivery',
            subtitle: 'Confirm the handoff checklist.',
            onTap: inFlight
                ? null
                : () => _open(() =>
                    ProofOfDeliveryScreen(controller: widget.controller)),
          ),
        if (hasComplete)
          _StepEntry(
            key: const Key('dropoff-step-complete'),
            icon: Icons.task_alt,
            title: 'Complete delivery',
            subtitle: 'Backend-gated completion.',
            onTap: inFlight
                ? null
                : () => _open(() =>
                    CompleteDeliveryScreen(controller: widget.controller)),
          ),
        if (hasFail)
          _StepEntry(
            key: const Key('dropoff-step-fail'),
            icon: Icons.report_gmailerrorred_outlined,
            title: 'Report failed delivery',
            subtitle: "Use when you can't complete safely.",
            onTap: inFlight
                ? null
                : () => _open(() => AgeVerificationFailedScreen(
                    controller: widget.controller)),
          ),
      ],
    );
  }

  Widget _completedSummary(BuildContext context, AssignmentDetailState state) {
    final detail = state.detail;
    final order = detail?.order;
    final completedAt = detail?.completedAt ?? order?.deliveredAt;
    return NubeRushCard(
      key: const Key('dropoff-completed-summary'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.check_circle, color: NubeRushColors.success),
              const SizedBox(width: NubeRushSpacing.sm),
              Text('Delivery completed',
                  style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
          const SizedBox(height: NubeRushSpacing.md),
          if (detail != null) _line('Assignment', detail.status),
          if (order != null) _line('Order status', order.status),
          if (completedAt != null) _line('Completed', _fmt(completedAt)),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('dropoff-completed-done'),
            label: 'Done',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }

  Widget _notActive(BuildContext context, String? deliveryState) {
    return NubeRushCard(
      key: const Key('dropoff-not-active'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Dropoff isn’t the current step',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          Text(
            deliveryState == null
                ? 'There is no dropoff action available right now.'
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
      key: const Key('dropoff-action-error'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NubeRushInlineError(message: state.actionErrorMessage ?? ''),
        const SizedBox(height: NubeRushSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              key: const Key('dropoff-action-error-dismiss'),
              onPressed: inFlight ? null : widget.controller.clearActionError,
              child: const Text('Dismiss'),
            ),
            const SizedBox(width: NubeRushSpacing.sm),
            FilledButton(
              key: const Key('dropoff-action-error-reload'),
              onPressed: inFlight ? null : () => widget.controller.reload(),
              child: const Text('Reload'),
            ),
          ],
        ),
      ],
    );
  }

  // --- Helpers --------------------------------------------------------- //

  String _storeLabel(DriverAssignmentStore store) {
    final code = store.code.trim();
    return code.isEmpty ? store.name : '${store.name} (${store.code})';
  }

  static String _fmt(DateTime dt) {
    final l = dt.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${l.year}-${two(l.month)}-${two(l.day)} '
        '${two(l.hour)}:${two(l.minute)}';
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
                color: enabled
                    ? NubeRushColors.primary
                    : NubeRushColors.disabled),
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
                key: const Key('dropoff-retry'),
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
