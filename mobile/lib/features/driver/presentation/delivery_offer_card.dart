// NubeRush Driver — delivery offer card (Dr.1.5.D).
//
// A premium NubeRush card for a single offered assignment. It DISPLAYS only the
// PII-free summary the backend already returns (store name, order/assignment
// status) plus a short, non-sensitive assignment reference. It NEVER shows
// customer identity, address, coordinates, phone, invented instructions, or a
// restricted-product flag (the read model carries none). Accept/Decline call
// back to the controller — the card itself touches no endpoint.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_assignment.dart';
import 'delivery_offer_state.dart';

class DeliveryOfferCard extends StatelessWidget {
  const DeliveryOfferCard({
    super.key,
    required this.offer,
    required this.onAccept,
    required this.onDecline,
    this.actionsEnabled = true,
    this.runningAction,
  });

  final DriverAssignmentSummary offer;
  final VoidCallback onAccept;
  final VoidCallback onDecline;

  /// Disabled while any offer action is in flight anywhere on the surface.
  final bool actionsEnabled;

  /// Non-null when THIS offer has an action running (drives the spinner).
  final OfferAction? runningAction;

  /// Short, non-sensitive reference (the assignment id is not PII).
  String get _shortRef =>
      offer.id.length > 8 ? offer.id.substring(0, 8) : offer.id;

  @override
  Widget build(BuildContext context) {
    final title = offer.storeName?.trim().isNotEmpty == true
        ? offer.storeName!.trim()
        : 'Order $_shortRef';
    final accepting = runningAction == OfferAction.accept;
    final declining = runningAction == OfferAction.decline;

    return NubeRushCard(
      key: Key('offer-card-${offer.id}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.local_offer, color: NubeRushColors.primary),
              const SizedBox(width: NubeRushSpacing.sm),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 17,
                  ),
                ),
              ),
              const _OfferBadge(),
            ],
          ),
          const SizedBox(height: NubeRushSpacing.md),
          _line('Offer', '#$_shortRef'),
          _line('Assignment', offer.status),
          if (offer.orderStatus != null) _line('Order', offer.orderStatus!),
          const SizedBox(height: NubeRushSpacing.lg),
          Row(
            children: [
              Expanded(
                child: NubeRushSecondaryButton(
                  key: Key('offer-decline-${offer.id}'),
                  label: 'Decline',
                  isLoading: declining,
                  onPressed: actionsEnabled ? onDecline : null,
                ),
              ),
              const SizedBox(width: NubeRushSpacing.md),
              Expanded(
                child: NubeRushPrimaryButton(
                  key: Key('offer-accept-${offer.id}'),
                  label: 'Accept',
                  isLoading: accepting,
                  onPressed: actionsEnabled ? onAccept : null,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _line(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
        child: Row(
          children: [
            Text(
              '$label: ',
              style: const TextStyle(color: NubeRushColors.textSecondary),
            ),
            Expanded(
              child: Text(
                value,
                style: const TextStyle(color: NubeRushColors.textPrimary),
              ),
            ),
          ],
        ),
      );
}

class _OfferBadge extends StatelessWidget {
  const _OfferBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.sm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: NubeRushColors.primary.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: NubeRushColors.primary),
      ),
      child: const Text(
        'OFFER',
        style: TextStyle(
          color: NubeRushColors.primary,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1,
        ),
      ),
    );
  }
}
