// NubeRush Driver — assignment detail + delivery-state + operational actions
// (Dr.1.3.F + .G + .H + .I).
//
// Dr.1.3.I: an action failure on a loaded screen shows a non-destructive inline
// action-error card (reload = GET-only refresh, dismiss = clear) and keeps the
// loaded detail/delivery-state visible. Full-screen error/offline/
// unauthenticated remain only for initial-load failures with no loaded data.
//
// Displays the backend-reported assignment lifecycle status, PII-free order
// status, store context, and the delivery operational `state`. Dr.1.3.G adds
// OPERATIONAL action buttons (accept / decline / start / arrive-store /
// pickup / depart-to-customer / arrive-customer) which are offered from a
// conservative, display-only mapping of the backend state. The backend is the
// authority: an invalid action surfaces as a normal error and state is re-read.
//
// It NEVER shows COMPLIANCE actions (verify-age / proof / complete / fail /
// return-to-store / confirm-driver-return), compliance UI, or fake
// map/route/ETA/earnings, and never computes a transition locally.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import '../domain/driver_assignment.dart';
import 'active_delivery_summary_card.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'compliance_dialogs.dart';
import 'compliance_status_card.dart';
import 'delivery_timeline.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';
import 'dropoff_support_screen.dart';
import 'failed_return_flow.dart';
import 'failed_return_flow_screen.dart';
import 'next_action_panel.dart';
import 'pickup_support_screen.dart';

class AssignmentDetailScreen extends StatefulWidget {
  const AssignmentDetailScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<AssignmentDetailScreen> createState() => _AssignmentDetailScreenState();
}

class _AssignmentDetailScreenState extends State<AssignmentDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.load();
    });
  }

  Future<void> _onAction(
    BuildContext context,
    DriverOperationalAction action,
  ) async {
    if (action.requiresConfirmation) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(action.label),
          content: Text(action.confirmCopy ?? 'Are you sure?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              key: const Key('action-confirm'),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Confirm'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    await widget.controller.runAction(action);
  }

  Future<void> _onCompliance(
    BuildContext context,
    DriverComplianceAction action,
    String? deliveryState,
  ) async {
    switch (action) {
      case DriverComplianceAction.verifyAge:
        final req = await showVerifyAgeDialog(context);
        if (req != null) await widget.controller.verifyAge(req);
      case DriverComplianceAction.submitProof:
        final req = await showProofDialog(context);
        if (req != null) await widget.controller.submitProof(req);
      case DriverComplianceAction.completeDelivery:
        if (await showCompleteConfirm(context)) {
          await widget.controller.completeDelivery();
        }
      case DriverComplianceAction.reportFailedDelivery:
        final req = await showFailDialog(context);
        if (req != null) await widget.controller.failDelivery(req);
      case DriverComplianceAction.returnToStore:
        // start while delivery_failed; arrive while returning_to_store.
        final returnAction = deliveryState == 'returning_to_store'
            ? ReturnAction.arrive
            : ReturnAction.start;
        final req = await showReturnToStoreDialog(context, returnAction);
        if (req != null) await widget.controller.returnToStore(req);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Dr.1.5.L: align the Active Delivery surface with the brand scaffold used
    // by the other Dr.1.5 screens (NubeRushScaffold already wraps a SafeArea).
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Active delivery')),
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
          key: Key('assignment-detail-loading'),
          child: NubeRushLoadingState(),
        );
      case AssignmentDetailStatus.unauthenticated:
        return const _Message(
          key: Key('assignment-detail-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case AssignmentDetailStatus.offline:
        return _Message(
          key: const Key('assignment-detail-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case AssignmentDetailStatus.error:
        return _Message(
          key: const Key('assignment-detail-error'),
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
    final complianceActions = detail == null
        ? const <DriverComplianceAction>[]
        : complianceActionsFor(
            assignmentStatus: detail.status,
            deliveryState: deliveryState?.state,
          );

    // Eager Column (not a lazy ListView): the Active Delivery Overview adds
    // several cards above the action groups, and an eager scroll view keeps
    // every card built so tests/scrolling can always reach the actions below.
    return SingleChildScrollView(
      key: const Key('assignment-detail-loaded'),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Dr.1.3.I: non-destructive inline action error. The loaded detail
          // below stays visible; reload re-fetches GET data, dismiss clears it.
          if (state.actionErrorMessage != null) ...[
          _actionErrorCard(context, state),
          const SizedBox(height: 16),
        ],
        // Dr.1.5.E: Active Delivery Overview — mission summary, timeline, next
        // action, and compliance status (all display-only from existing data).
        if (detail != null) ...[
          ActiveDeliverySummaryCard(
            detail: detail,
            deliveryState: deliveryState,
          ),
          const SizedBox(height: 16),
          // Dr.1.5.F: contextual entry into the dedicated pickup support flow,
          // shown only while a pickup-stage action (arrive-store / pickup) is
          // available. It never replaces the action groups below.
          if (_isPickupStage(actions)) ...[
            _pickupEntryCard(context),
            const SizedBox(height: 16),
          ],
          // Dr.1.5.G: contextual entry into the dedicated dropoff/compliance
          // flow, shown during the customer-dropoff stage. It never replaces
          // the action/compliance groups below.
          if (_isDropoffStage(detail, actions, complianceActions)) ...[
            _dropoffEntryCard(context),
            const SizedBox(height: 16),
          ],
          // Dr.1.5.H: contextual entry into the dedicated failed-delivery /
          // return flow, shown only when fail / return-to-store actions or a
          // returned/pending state are relevant. It never replaces the
          // operational/compliance action groups below.
          if (failedReturnRelevant(
            compliance: complianceActions,
            detail: detail,
            deliveryState: deliveryState,
          )) ...[
            _failedReturnEntryCard(context, complianceActions),
            const SizedBox(height: 16),
          ],
          DeliveryTimeline(state: deliveryState?.state),
          const SizedBox(height: 16),
          NextActionPanel(
            operationalActions: actions,
            complianceActions: complianceActions,
          ),
          const SizedBox(height: 16),
          ComplianceStatusCard(complianceActions: complianceActions),
        ],
        // Existing operational/compliance action groups (Dr.1.3.G/.H/.I) are
        // preserved unchanged — the backend remains the authority.
        if (actions.isNotEmpty) ...[
          const SizedBox(height: 16),
          _actionsCard(context, state, actions),
        ],
        if (complianceActions.isNotEmpty) ...[
          const SizedBox(height: 16),
          _complianceCard(
            context,
            state,
            complianceActions,
            deliveryState?.state,
          ),
        ],
        ],
      ),
    );
  }

  /// True while a store-pickup action (arrive-store / pickup) is available.
  bool _isPickupStage(List<DriverOperationalAction> actions) =>
      actions.contains(DriverOperationalAction.arriveStore) ||
      actions.contains(DriverOperationalAction.pickup);

  /// Contextual entry into the dedicated pickup support flow. Reuses the same
  /// controller so the pickup surface shares the loaded detail/delivery-state.
  Widget _pickupEntryCard(BuildContext context) {
    return NubeRushCard(
      key: const Key('pickup-support-entry'),
      onTap: () => _openPickupSupport(context),
      child: Row(
        children: [
          const Icon(Icons.store_mall_directory_outlined,
              color: NubeRushColors.primary),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Store pickup',
                  style: TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                const Text(
                  'Open the guided pickup steps.',
                  style: TextStyle(
                    color: NubeRushColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }

  void _openPickupSupport(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PickupSupportScreen(controller: widget.controller),
      ),
    );
  }

  /// True during the customer-dropoff stage: arrive-customer is offered, a
  /// dropoff compliance step (verify-age / proof / complete / fail) is offered,
  /// or the delivery is already completed.
  bool _isDropoffStage(
    DriverAssignmentDetail? detail,
    List<DriverOperationalAction> actions,
    List<DriverComplianceAction> compliance,
  ) {
    if (actions.contains(DriverOperationalAction.arriveCustomer)) return true;
    const dropoff = <DriverComplianceAction>{
      DriverComplianceAction.verifyAge,
      DriverComplianceAction.submitProof,
      DriverComplianceAction.completeDelivery,
      DriverComplianceAction.reportFailedDelivery,
    };
    if (compliance.any(dropoff.contains)) return true;
    return detail?.status == 'completed';
  }

  Widget _dropoffEntryCard(BuildContext context) {
    return NubeRushCard(
      key: const Key('dropoff-support-entry'),
      onTap: () => _openDropoffSupport(context),
      child: Row(
        children: [
          const Icon(Icons.handshake_outlined, color: NubeRushColors.primary),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Customer dropoff',
                  style: TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                const Text(
                  'Open the guided dropoff & compliance steps.',
                  style: TextStyle(
                    color: NubeRushColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }

  void _openDropoffSupport(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DropoffSupportScreen(controller: widget.controller),
      ),
    );
  }

  /// Contextual entry into the dedicated failed-delivery / return flow. Reuses
  /// the same controller so the flow shares the loaded detail/delivery-state.
  Widget _failedReturnEntryCard(
    BuildContext context,
    List<DriverComplianceAction> complianceActions,
  ) {
    final stage = failedReturnStage(
      compliance: complianceActions,
      detail: widget.controller.state.detail,
      deliveryState: widget.controller.state.deliveryState,
    );
    final (title, subtitle) = switch (stage) {
      FailedReturnStage.reportFail => (
          'Failed delivery',
          'Report a delivery you can’t complete.',
        ),
      FailedReturnStage.returnToStore => (
          'Return to store',
          'This order needs to go back to the store.',
        ),
      FailedReturnStage.returnPending => (
          'Return pending',
          'Awaiting store / NubeRush confirmation.',
        ),
      FailedReturnStage.notRelevant => (
          'Failed delivery / Return',
          'Open the failed-delivery & return steps.',
        ),
    };
    return NubeRushCard(
      key: const Key('failed-return-entry'),
      onTap: () => _openFailedReturn(context),
      child: Row(
        children: [
          const Icon(Icons.assignment_return_outlined,
              color: NubeRushColors.primary),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: NubeRushColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }

  void _openFailedReturn(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => FailedReturnFlowScreen(controller: widget.controller),
      ),
    );
  }

  Widget _actionErrorCard(BuildContext context, AssignmentDetailState state) {
    // Disable the reload/dismiss controls while another action is running so we
    // never reload or clear mid-flight.
    final inFlight = state.isActionInFlight;
    // Dr.1.5.L: use the shared brand inline-error primitive (matches the
    // dropoff / failed-return surfaces) instead of an ad-hoc Material Card +
    // colorScheme.errorContainer. Behavior is unchanged: non-destructive, with
    // a GET-only reload and a dismiss, both disabled while an action runs.
    return Column(
      key: const Key('assignment-detail-action-error'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NubeRushInlineError(message: state.actionErrorMessage ?? ''),
        const SizedBox(height: NubeRushSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              key: const Key('action-error-dismiss'),
              onPressed:
                  inFlight ? null : widget.controller.clearActionError,
              child: const Text('Dismiss'),
            ),
            const SizedBox(width: NubeRushSpacing.sm),
            FilledButton(
              key: const Key('action-error-reload'),
              onPressed: inFlight ? null : () => widget.controller.reload(),
              child: const Text('Reload'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _actionsCard(
    BuildContext context,
    AssignmentDetailState state,
    List<DriverOperationalAction> actions,
  ) {
    final inFlight = state.isActionInFlight;
    return NubeRushCard(
      key: const Key('assignment-detail-actions'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Actions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.sm),
          for (final action in actions)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
              child: FilledButton(
                key: Key('action-${action.id}'),
                // Disable every button while any action is in flight.
                onPressed: inFlight ? null : () => _onAction(context, action),
                child: state.runningAction == action
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(action.label),
              ),
            ),
        ],
      ),
    );
  }

  Widget _complianceCard(
    BuildContext context,
    AssignmentDetailState state,
    List<DriverComplianceAction> actions,
    String? deliveryState,
  ) {
    final inFlight = state.isActionInFlight;
    return NubeRushCard(
      key: const Key('assignment-detail-compliance'),
      child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Compliance', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: NubeRushSpacing.sm),
            for (final action in actions)
              Padding(
                padding:
                    const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
                child: FilledButton.tonal(
                  key: Key('compliance-${action.id}'),
                  onPressed: inFlight
                      ? null
                      : () => _onCompliance(context, action, deliveryState),
                  child: state.runningComplianceAction == action
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(action.label),
                ),
              ),
          ],
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
    // Dr.1.5.L: brand-consistent message view (matches the other Dr.1.5
    // full-screen states — muted icon/spacing tokens).
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
                key: const Key('assignment-detail-retry'),
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
