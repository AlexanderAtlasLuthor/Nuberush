// NubeRush Driver — delivery history screen (Dr.1.5.K).
//
// A driver-safe history surface built ONLY from
// `GET /driver/assignments?status=<terminal>`. One terminal filter is active at
// a time (completed / canceled / declined / expired); switching a chip re-runs a
// safe GET. It shows loading / empty / error / offline / unauthenticated states,
// a retry that re-runs only the safe GET, and PII-free history cards. It calls
// no /orders/*, builds no fake history, and shows no earnings/payouts/taxes.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'delivery_history_controller.dart';
import 'delivery_history_state.dart';
import 'history_assignment_card.dart';

class DeliveryHistoryScreen extends StatefulWidget {
  const DeliveryHistoryScreen({
    super.key,
    required this.controller,
    this.onOpenAssignment,
  });

  final DeliveryHistoryController controller;

  /// Optional read-only detail navigation reusing the existing assignment
  /// detail screen (wired by the app shell). When null, cards are summary-only.
  final void Function(BuildContext context, DriverAssignmentSummary assignment)?
      onOpenAssignment;

  @override
  State<DeliveryHistoryScreen> createState() => _DeliveryHistoryScreenState();
}

class _DeliveryHistoryScreenState extends State<DeliveryHistoryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('History')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _filterChips(state),
              Expanded(child: _body(context, state)),
            ],
          );
        },
      ),
    );
  }

  Widget _filterChips(DeliveryHistoryState state) {
    final inFlight = state.status == DeliveryHistoryStatus.loading;
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.lg,
        vertical: NubeRushSpacing.md,
      ),
      child: Wrap(
        key: const Key('history-filters'),
        spacing: NubeRushSpacing.sm,
        children: [
          for (final f in HistoryFilter.values)
            ChoiceChip(
              key: Key('history-filter-${f.wire}'),
              label: Text(f.label),
              selected: state.filter == f,
              selectedColor: NubeRushColors.primary,
              backgroundColor: NubeRushColors.surfaceMuted,
              labelStyle: TextStyle(
                color: state.filter == f
                    ? NubeRushColors.onPrimary
                    : NubeRushColors.textPrimary,
              ),
              onSelected: inFlight
                  ? null
                  : (_) {
                      if (state.filter != f) {
                        widget.controller.selectFilter(f);
                      }
                    },
            ),
        ],
      ),
    );
  }

  Widget _body(BuildContext context, DeliveryHistoryState state) {
    switch (state.status) {
      case DeliveryHistoryStatus.initial:
      case DeliveryHistoryStatus.loading:
        return const Center(
          key: Key('history-loading'),
          child: NubeRushLoadingState(),
        );
      case DeliveryHistoryStatus.empty:
        return _Message(
          key: const Key('history-empty'),
          icon: Icons.inbox_outlined,
          message: 'No ${state.filter.label.toLowerCase()} deliveries yet.',
        );
      case DeliveryHistoryStatus.unauthenticated:
        return const _Message(
          key: Key('history-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case DeliveryHistoryStatus.offline:
        return _Message(
          key: const Key('history-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case DeliveryHistoryStatus.error:
        return _Message(
          key: const Key('history-error'),
          icon: Icons.error_outline,
          message: state.errorMessage ?? 'Something went wrong.',
          onRetry: widget.controller.retry,
        );
      case DeliveryHistoryStatus.loaded:
        return ListView.builder(
          key: const Key('history-loaded'),
          padding: const EdgeInsets.fromLTRB(
            NubeRushSpacing.lg,
            0,
            NubeRushSpacing.lg,
            NubeRushSpacing.lg,
          ),
          itemCount: state.assignments.length,
          itemBuilder: (context, index) {
            final a = state.assignments[index];
            return Padding(
              padding: const EdgeInsets.only(bottom: NubeRushSpacing.md),
              child: HistoryAssignmentCard(
                assignment: a,
                onOpen: widget.onOpenAssignment == null
                    ? null
                    : () => widget.onOpenAssignment!(context, a),
              ),
            );
          },
        );
    }
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
                key: const Key('history-retry'),
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
