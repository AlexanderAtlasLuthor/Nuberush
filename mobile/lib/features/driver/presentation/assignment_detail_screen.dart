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

import '../domain/compliance_requests.dart';
import '../domain/driver_assignment.dart';
import '../domain/driver_delivery_state.dart';
import 'assignment_detail_controller.dart';
import 'assignment_detail_state.dart';
import 'compliance_dialogs.dart';
import 'driver_compliance_action.dart';
import 'driver_operational_action.dart';

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
    return Scaffold(
      appBar: AppBar(title: const Text('Assignment')),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: widget.controller,
          builder: (context, _) => _body(context, widget.controller.state),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, AssignmentDetailState state) {
    switch (state.status) {
      case AssignmentDetailStatus.initial:
      case AssignmentDetailStatus.loading:
        return const Center(
          key: Key('assignment-detail-loading'),
          child: CircularProgressIndicator(),
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

    return ListView(
      key: const Key('assignment-detail-loaded'),
      padding: const EdgeInsets.all(16),
      children: [
        // Dr.1.3.I: non-destructive inline action error. The loaded detail
        // below stays visible; reload re-fetches GET data, dismiss clears it.
        if (state.actionErrorMessage != null) ...[
          _actionErrorCard(context, state),
          const SizedBox(height: 16),
        ],
        if (detail != null) _assignmentCard(context, detail),
        const SizedBox(height: 16),
        if (deliveryState != null) _deliveryStateCard(context, deliveryState),
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
    );
  }

  Widget _actionErrorCard(BuildContext context, AssignmentDetailState state) {
    final scheme = Theme.of(context).colorScheme;
    // Disable the reload/dismiss controls while another action is running so we
    // never reload or clear mid-flight.
    final inFlight = state.isActionInFlight;
    return Card(
      key: const Key('assignment-detail-action-error'),
      color: scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  state.actionErrorIsOffline
                      ? Icons.wifi_off
                      : Icons.error_outline,
                  color: scheme.onErrorContainer,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    state.actionErrorMessage ?? '',
                    style: TextStyle(color: scheme.onErrorContainer),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  key: const Key('action-error-dismiss'),
                  onPressed: inFlight
                      ? null
                      : widget.controller.clearActionError,
                  child: const Text('Dismiss'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  key: const Key('action-error-reload'),
                  onPressed: inFlight ? null : () => widget.controller.reload(),
                  child: const Text('Reload'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _assignmentCard(BuildContext context, DriverAssignmentDetail detail) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Assignment', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Status: ${detail.status}'),
            if (detail.store != null) Text('Store: ${detail.store!.name}'),
            if (detail.order != null)
              Text('Order status: ${detail.order!.status}'),
          ],
        ),
      ),
    );
  }

  Widget _deliveryStateCard(
    BuildContext context,
    DriverDeliveryState deliveryState,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Delivery state',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('State: ${deliveryState.state}'),
          ],
        ),
      ),
    );
  }

  Widget _actionsCard(
    BuildContext context,
    AssignmentDetailState state,
    List<DriverOperationalAction> actions,
  ) {
    final inFlight = state.isActionInFlight;
    return Card(
      key: const Key('assignment-detail-actions'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Actions', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final action in actions)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
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
    return Card(
      key: const Key('assignment-detail-compliance'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Compliance', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final action in actions)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
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
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
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
