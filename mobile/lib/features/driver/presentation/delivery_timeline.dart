// NubeRush Driver — delivery timeline (Dr.1.5.E).
//
// A DISPLAY-ONLY visual timeline derived from the backend-reported delivery
// operational `state` string. It computes NO authority: it never advances or
// mutates state, never claims completion the backend didn't report, and renders
// a safe fallback for terminal/exception/unknown states. The raw backend state
// strings are the single source of truth.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_radii.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

enum TimelineStepStatus { done, current, upcoming }

class DeliveryTimelineStep {
  const DeliveryTimelineStep(this.label, this.status);
  final String label;
  final TimelineStepStatus status;
}

/// The computed, display-only timeline for a given delivery state.
class DeliveryTimelineView {
  const DeliveryTimelineView({required this.steps, this.exceptionLabel});

  final List<DeliveryTimelineStep> steps;

  /// Non-null for terminal/exception/unknown/empty states. When set, no linear
  /// step is marked current — the label communicates the real backend state.
  final String? exceptionLabel;

  bool get hasException => exceptionLabel != null;
}

/// Canonical, ordered happy-path labels. Conservative and display-only.
const List<String> kDeliveryTimelineLabels = <String>[
  'Accepted',
  'En route to store',
  'At store',
  'Picked up',
  'En route to customer',
  'At customer',
  'Verification',
  'Completed',
];

/// Maps a known delivery state to its canonical step index.
const Map<String, int> _stateIndex = <String, int>{
  'not_started': 0,
  'en_route_to_store': 1,
  'arrived_at_store': 2,
  'pickup_started': 2,
  'picked_up': 3,
  'en_route_to_customer': 4,
  'arrived_at_customer': 5,
  'id_verification_pending': 6,
  'id_verified': 6,
  'delivery_completed': 7,
};

/// Terminal/branch states that are not a single point on the linear path.
const Map<String, String> _exceptionLabels = <String, String>{
  'delivery_failed': 'Delivery failed',
  'returning_to_store': 'Returning to store',
  'returned_to_store': 'Returned to store',
  'canceled': 'Canceled',
};

/// Pure, testable timeline builder. Never throws; unknown input is safe.
DeliveryTimelineView buildDeliveryTimeline(String? state) {
  List<DeliveryTimelineStep> allUpcoming() => kDeliveryTimelineLabels
      .map((l) => DeliveryTimelineStep(l, TimelineStepStatus.upcoming))
      .toList(growable: false);

  final raw = state?.trim() ?? '';
  if (raw.isEmpty) {
    return DeliveryTimelineView(
      steps: allUpcoming(),
      exceptionLabel: 'Waiting for delivery state',
    );
  }
  final exception = _exceptionLabels[raw];
  if (exception != null) {
    return DeliveryTimelineView(steps: allUpcoming(), exceptionLabel: exception);
  }
  final current = _stateIndex[raw];
  if (current == null) {
    // Unknown state: never guess progress — show a safe fallback.
    return DeliveryTimelineView(
      steps: allUpcoming(),
      exceptionLabel: 'Current state: $raw',
    );
  }
  final steps = <DeliveryTimelineStep>[];
  for (var i = 0; i < kDeliveryTimelineLabels.length; i++) {
    final TimelineStepStatus status;
    if (i < current) {
      status = TimelineStepStatus.done;
    } else if (i == current) {
      status = TimelineStepStatus.current;
    } else {
      status = TimelineStepStatus.upcoming;
    }
    steps.add(DeliveryTimelineStep(kDeliveryTimelineLabels[i], status));
  }
  return DeliveryTimelineView(steps: steps);
}

class DeliveryTimeline extends StatelessWidget {
  const DeliveryTimeline({super.key, required this.state});

  /// Raw backend delivery operational state (may be null/unknown).
  final String? state;

  @override
  Widget build(BuildContext context) {
    final view = buildDeliveryTimeline(state);
    return NubeRushCard(
      key: const Key('delivery-timeline'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Delivery timeline',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.md),
          if (view.hasException) ...[
            _ExceptionChip(label: view.exceptionLabel!),
            const SizedBox(height: NubeRushSpacing.md),
          ],
          for (var i = 0; i < view.steps.length; i++)
            _StepRow(
              step: view.steps[i],
              isLast: i == view.steps.length - 1,
            ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.step, required this.isLast});

  final DeliveryTimelineStep step;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final isCurrent = step.status == TimelineStepStatus.current;
    final isDone = step.status == TimelineStepStatus.done;
    final Color dotColor = isCurrent
        ? NubeRushColors.primary
        : isDone
            ? NubeRushColors.success
            : NubeRushColors.disabled;
    final Color textColor = isCurrent
        ? NubeRushColors.textPrimary
        : isDone
            ? NubeRushColors.textPrimary
            : NubeRushColors.textSecondary;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                key: isCurrent ? const Key('delivery-timeline-current') : null,
                height: 16,
                width: 16,
                decoration: BoxDecoration(
                  color: isCurrent ? dotColor : Colors.transparent,
                  border: Border.all(color: dotColor, width: 2),
                  shape: BoxShape.circle,
                ),
                child: isDone
                    ? const Icon(Icons.check,
                        size: 10, color: NubeRushColors.success)
                    : null,
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: NubeRushColors.border,
                  ),
                ),
            ],
          ),
          const SizedBox(width: NubeRushSpacing.md),
          Padding(
            padding: const EdgeInsets.only(bottom: NubeRushSpacing.md),
            child: Text(
              step.label,
              style: TextStyle(
                color: textColor,
                fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExceptionChip extends StatelessWidget {
  const _ExceptionChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('delivery-timeline-exception'),
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.md,
        vertical: NubeRushSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: NubeRushColors.surfaceMuted,
        borderRadius: NubeRushRadii.borderMd,
        border: Border.all(color: NubeRushColors.border),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline,
              size: 18, color: NubeRushColors.textSecondary),
          const SizedBox(width: NubeRushSpacing.sm),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: NubeRushColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}
