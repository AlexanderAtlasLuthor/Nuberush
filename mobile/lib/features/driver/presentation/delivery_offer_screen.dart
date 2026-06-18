// NubeRush Driver — Delivery Offer Surface (Dr.1.5.D).
//
// A dedicated screen that presents offered assignments (status == 'offered')
// as delivery offers, sourced ONLY from GET /driver/assignments. Accept/Decline
// use the existing bodyless endpoints; decline is confirmed locally and sends
// NO request body. On an action failure the loaded offer list stays visible and
// a non-destructive inline error is shown. No realtime, push, websocket,
// expiry, countdown, timers, or invented offers.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import 'delivery_offer_card.dart';
import 'delivery_offer_controller.dart';
import 'delivery_offer_state.dart';

class DeliveryOfferScreen extends StatefulWidget {
  const DeliveryOfferScreen({super.key, required this.controller});

  final DeliveryOfferController controller;

  @override
  State<DeliveryOfferScreen> createState() => _DeliveryOfferScreenState();
}

class _DeliveryOfferScreenState extends State<DeliveryOfferScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.load();
    });
  }

  Future<void> _onDecline(String assignmentId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const Key('offer-decline-dialog'),
        title: const Text('Decline offer'),
        content: const Text(
          'Decline this delivery offer? The backend records the decline only.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('offer-decline-confirm'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Decline'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await widget.controller.decline(assignmentId);
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Delivery offers')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) => _body(context, widget.controller.state),
      ),
    );
  }

  Widget _body(BuildContext context, DeliveryOfferState state) {
    switch (state.status) {
      case DeliveryOfferStatus.initial:
      case DeliveryOfferStatus.loading:
        return const Center(
          key: Key('offers-loading'),
          child: NubeRushLoadingState(),
        );
      case DeliveryOfferStatus.empty:
        return const _Message(
          key: Key('offers-empty'),
          icon: Icons.local_offer_outlined,
          message: 'No delivery offers right now.',
        );
      case DeliveryOfferStatus.unauthenticated:
        return const _Message(
          key: Key('offers-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case DeliveryOfferStatus.offline:
        return _Message(
          key: const Key('offers-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case DeliveryOfferStatus.error:
        return _Message(
          key: const Key('offers-error'),
          icon: Icons.error_outline,
          message: state.errorMessage ?? 'Something went wrong.',
          onRetry: widget.controller.retry,
        );
      case DeliveryOfferStatus.loaded:
        return _loaded(context, state);
    }
  }

  Widget _loaded(BuildContext context, DeliveryOfferState state) {
    final inFlight = state.isActionInFlight;
    return ListView(
      key: const Key('offers-loaded'),
      padding: const EdgeInsets.all(NubeRushSpacing.lg),
      children: [
        if (state.actionErrorMessage != null) ...[
          _actionErrorBanner(context, state),
          const SizedBox(height: NubeRushSpacing.lg),
        ],
        Padding(
          padding: const EdgeInsets.only(
            left: NubeRushSpacing.xs,
            bottom: NubeRushSpacing.md,
          ),
          child: Text(
            'These offers come from your current assignments — not a live '
            'dispatch feed.',
            style: const TextStyle(color: NubeRushColors.textSecondary,
                fontSize: 13),
          ),
        ),
        for (final offer in state.offers) ...[
          DeliveryOfferCard(
            offer: offer,
            actionsEnabled: !inFlight,
            runningAction:
                state.runningOfferId == offer.id ? state.runningAction : null,
            onAccept: () => widget.controller.accept(offer.id),
            onDecline: () => _onDecline(offer.id),
          ),
          const SizedBox(height: NubeRushSpacing.md),
        ],
      ],
    );
  }

  Widget _actionErrorBanner(BuildContext context, DeliveryOfferState state) {
    final inFlight = state.isActionInFlight;
    return Column(
      key: const Key('offers-action-error'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NubeRushInlineError(message: state.actionErrorMessage ?? ''),
        const SizedBox(height: NubeRushSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton(
              key: const Key('offers-action-error-dismiss'),
              onPressed: inFlight ? null : widget.controller.clearActionError,
              child: const Text('Dismiss'),
            ),
            const SizedBox(width: NubeRushSpacing.sm),
            FilledButton(
              key: const Key('offers-action-error-reload'),
              onPressed: inFlight ? null : () => widget.controller.reload(),
              child: const Text('Reload'),
            ),
          ],
        ),
      ],
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
                key: const Key('offers-retry'),
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
