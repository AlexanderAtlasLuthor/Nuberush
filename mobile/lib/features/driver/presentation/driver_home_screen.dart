// NubeRush Driver — Operations Home (Dr.1.5.C).
//
// Evolves the Dr.1.3.E read-only profile/eligibility screen into an operations
// dashboard. It still renders ONLY what `/driver/me` and `/driver/eligibility`
// return — no assignments fetch here, no action buttons, no compliance UI, no
// fake operational/earnings/route data. New for Dr.1.5.C:
//   - A readiness/status card and (when blocked) an eligibility blockers card.
//   - A PRESENTATION-ONLY online/offline affordance. Its state lives only in
//     widget memory: no repository call, no API call, no storage, no Supabase
//     write, and it never claims the backend is dispatching offers. It can only
//     show "online" when the backend says `can_go_online` is true.
//   - Operational entry points (Assignments / Offers / Active Delivery /
//     Safety & Support / History). Assignments/Offers/Active reuse the existing
//     read-only assignment-list navigation; Safety & Support opens the static
//     safety surface (Dr.1.5.J); History opens the terminal-assignment history
//     surface (Dr.1.5.K). Entries that need a wired callback render disabled
//     when it is absent.
//
// Flutter presents. Backend decides. Nothing here computes eligibility,
// availability, or any business rule locally.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/driver_eligibility.dart';
import '../domain/driver_profile.dart';
import 'driver_home_controller.dart';
import 'driver_home_state.dart';
import 'safety_toolkit_screen.dart';

const String kDriverHomeTitle = 'NubeRush Driver';

/// Honest disclaimer copy: the local toggle is presentation only.
const String kOnlineDispatchDisclaimer =
    'Actual dispatch availability is managed by NubeRush.';

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({
    super.key,
    required this.controller,
    this.onViewAssignments,
    this.onViewOffers,
    this.onViewHistory,
    this.appBarActions = const <Widget>[],
  });

  final DriverHomeController controller;

  /// Optional read-only navigation to the assignments list (wired by the app
  /// shell). When null, the operational entry points that depend on it render
  /// as disabled "coming next" cards. Presentation only — no business logic.
  final void Function(BuildContext context)? onViewAssignments;

  /// Optional navigation to the dedicated Delivery Offer Surface (Dr.1.5.D).
  /// When null, the Offers entry falls back to [onViewAssignments] (offered
  /// assignments still live in the list). Presentation only.
  final void Function(BuildContext context)? onViewOffers;

  /// Optional navigation to the Delivery History surface (Dr.1.5.K). When null,
  /// the History entry renders disabled (it never makes a backend call until
  /// the History screen itself opens). Presentation only.
  final void Function(BuildContext context)? onViewHistory;

  /// Extra trailing app-bar actions injected by the app shell (e.g. the
  /// authenticated shell's logout button). Default empty preserves the prior
  /// read-only home. Presentation only — no business logic.
  final List<Widget> appBarActions;

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
  /// Presentation-only "online" intent. Lives only here — never persisted,
  /// never sent to the backend, never read from storage. Reset to offline on
  /// every build of the screen (fresh session = offline presentation).
  bool _presentationOnline = false;

  @override
  void initState() {
    super.initState();
    // Kick off the first load after the initial frame.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(
        title: const Text(kDriverHomeTitle),
        actions: [
          if (widget.onViewAssignments != null)
            IconButton(
              key: const Key('driver-home-view-assignments'),
              tooltip: 'Assignments',
              icon: const Icon(Icons.list_alt),
              onPressed: () => widget.onViewAssignments!(context),
            ),
          ...widget.appBarActions,
        ],
      ),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) => _body(context, widget.controller.state),
      ),
    );
  }

  Widget _body(BuildContext context, DriverHomeState state) {
    switch (state.status) {
      case DriverHomeStatus.initial:
      case DriverHomeStatus.loading:
        return const Center(
          key: Key('driver-home-loading'),
          child: NubeRushLoadingState(),
        );
      case DriverHomeStatus.unauthenticated:
        return const _MessageView(
          key: Key('driver-home-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case DriverHomeStatus.offline:
        return _MessageView(
          key: const Key('driver-home-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case DriverHomeStatus.error:
        return _MessageView(
          key: const Key('driver-home-error'),
          icon: Icons.error_outline,
          message: state.errorMessage ?? 'Something went wrong.',
          onRetry: widget.controller.retry,
        );
      case DriverHomeStatus.loaded:
        return _loaded(context, state);
    }
  }

  Widget _loaded(BuildContext context, DriverHomeState state) {
    final profile = state.profile;
    final eligibility = state.eligibility;
    final canGoOnline = eligibility?.canGoOnline ?? false;
    // Never present as online when the backend says the driver isn't eligible.
    final presentingOnline = canGoOnline && _presentationOnline;

    return ListView(
      key: const Key('driver-home-loaded'),
      padding: const EdgeInsets.all(NubeRushSpacing.lg),
      children: [
        const NubeRushBrandHeader(subtitle: 'DRIVER OPERATIONS'),
        const SizedBox(height: NubeRushSpacing.xl),
        if (profile != null) ...[
          _statusCard(context, profile, eligibility),
          const SizedBox(height: NubeRushSpacing.lg),
        ],
        if (eligibility != null) ...[
          _onlineCard(context, eligibility, presentingOnline),
          const SizedBox(height: NubeRushSpacing.lg),
        ],
        if (eligibility != null && eligibility.blockers.isNotEmpty) ...[
          _blockersCard(context, eligibility),
          const SizedBox(height: NubeRushSpacing.lg),
        ],
        _operationsSection(context, presentingOnline: presentingOnline),
      ],
    );
  }

  // --- Cards ----------------------------------------------------------- //

  Widget _statusCard(
    BuildContext context,
    DriverProfile profile,
    DriverEligibility? eligibility,
  ) {
    final ready = eligibility?.canGoOnline ?? false;
    return NubeRushCard(
      key: const Key('driver-home-status-card'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _cardTitle(context, 'Driver status'),
          const SizedBox(height: NubeRushSpacing.sm),
          _statusLine('Status', profile.status),
          _statusLine('Approval', profile.approvalStatus),
          const SizedBox(height: NubeRushSpacing.md),
          _readinessChip(ready),
        ],
      ),
    );
  }

  Widget _onlineCard(
    BuildContext context,
    DriverEligibility eligibility,
    bool presentingOnline,
  ) {
    final canGoOnline = eligibility.canGoOnline;
    return NubeRushCard(
      key: const Key('driver-home-online-card'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _cardTitle(context, 'Online presentation'),
          const SizedBox(height: NubeRushSpacing.sm),
          // Preserve the Dr.1.3.E eligibility copy for continuity.
          Text(
            canGoOnline ? 'You can go online.' : 'You cannot go online yet.',
            style: const TextStyle(color: NubeRushColors.textPrimary),
          ),
          if (canGoOnline) ...[
            const SizedBox(height: NubeRushSpacing.sm),
            SwitchListTile(
              key: const Key('driver-home-online-toggle'),
              contentPadding: EdgeInsets.zero,
              activeThumbColor: NubeRushColors.primary,
              title: Text(
                presentingOnline
                    ? 'Presentation mode: online'
                    : 'Presentation mode: offline',
                style: const TextStyle(color: NubeRushColors.textPrimary),
              ),
              subtitle: Text(
                presentingOnline
                    ? 'You look ready to drive.'
                    : 'Flip on when you are ready to drive.',
                style: const TextStyle(color: NubeRushColors.textSecondary),
              ),
              value: presentingOnline,
              // Local-only: no repository/API/storage write.
              onChanged: (next) =>
                  setState(() => _presentationOnline = next),
            ),
          ],
          const SizedBox(height: NubeRushSpacing.sm),
          Text(
            key: const Key('driver-home-online-disclaimer'),
            kOnlineDispatchDisclaimer,
            style: const TextStyle(
              color: NubeRushColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _blockersCard(BuildContext context, DriverEligibility eligibility) {
    return NubeRushCard(
      key: const Key('driver-home-blockers-card'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _cardTitle(context, 'Before you can go online'),
          const SizedBox(height: NubeRushSpacing.sm),
          for (final blocker in eligibility.blockers)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
              child: Text(
                '• ${blocker.message}',
                style: const TextStyle(color: NubeRushColors.textPrimary),
              ),
            ),
        ],
      ),
    );
  }

  Widget _operationsSection(
    BuildContext context, {
    required bool presentingOnline,
  }) {
    final onAssignments = widget.onViewAssignments;
    // Offers opens the dedicated surface when wired, else falls back to the
    // assignment list (offered assignments live there too).
    final onOffers = widget.onViewOffers ?? onAssignments;
    void open(BuildContext ctx) => onAssignments?.call(ctx);
    void openOffers(BuildContext ctx) => onOffers?.call(ctx);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(
            left: NubeRushSpacing.xs,
            bottom: NubeRushSpacing.sm,
          ),
          child: Text(
            'Operations',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        _OpsEntry(
          key: const Key('driver-home-ops-assignments'),
          icon: Icons.list_alt,
          title: 'Assignments',
          subtitle: 'View your assigned deliveries.',
          onTap: onAssignments == null ? null : () => open(context),
        ),
        const SizedBox(height: NubeRushSpacing.md),
        _OpsEntry(
          key: const Key('driver-home-ops-offers'),
          icon: Icons.local_offer_outlined,
          title: 'Offers',
          subtitle: 'Review and accept delivery offers.',
          onTap: onOffers == null ? null : () => openOffers(context),
        ),
        const SizedBox(height: NubeRushSpacing.md),
        _OpsEntry(
          key: const Key('driver-home-ops-active'),
          icon: Icons.local_shipping_outlined,
          title: 'Active delivery',
          subtitle: 'Continue an in-progress delivery.',
          onTap: onAssignments == null ? null : () => open(context),
        ),
        const SizedBox(height: NubeRushSpacing.md),
        _OpsEntry(
          key: const Key('driver-home-ops-safety'),
          icon: Icons.health_and_safety_outlined,
          title: 'Safety & support',
          subtitle: 'Safety tools, emergency guidance & support.',
          // Static/local-only surface (Dr.1.5.J). Opens without backend data
          // and works even with no active assignment.
          onTap: () => _openSafety(context),
        ),
        const SizedBox(height: NubeRushSpacing.md),
        _OpsEntry(
          key: const Key('driver-home-ops-history'),
          icon: Icons.history,
          title: 'History',
          subtitle: 'Review your past deliveries.',
          // Dr.1.5.K: opens the history surface (terminal assignments). No
          // backend call is made until the History screen itself loads.
          onTap: widget.onViewHistory == null
              ? null
              : () => widget.onViewHistory!(context),
        ),
      ],
    );
  }

  /// Opens the static/local Safety & support surface (Dr.1.5.J). Pure local
  /// navigation — no backend data required, no repository/API call.
  void _openSafety(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const SafetyToolkitScreen()),
    );
  }

  // --- Small presentation helpers -------------------------------------- //

  Widget _cardTitle(BuildContext context, String text) => Text(
        text,
        style: Theme.of(context).textTheme.titleMedium,
      );

  Widget _statusLine(String label, String value) => Padding(
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

  Widget _readinessChip(bool ready) {
    final color = ready ? NubeRushColors.success : NubeRushColors.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: NubeRushSpacing.md,
        vertical: NubeRushSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color),
      ),
      child: Text(
        ready ? 'Ready to go online' : 'Not ready yet',
        style: TextStyle(color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// A single operational entry-point card. Pure presentation: it only invokes
/// the [onTap] it is given (or renders disabled). It never calls an endpoint.
class _OpsEntry extends StatelessWidget {
  const _OpsEntry({
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
    final titleColor =
        enabled ? NubeRushColors.textPrimary : NubeRushColors.textSecondary;
    return NubeRushCard(
      onTap: onTap,
      child: Row(
        children: [
          Icon(
            icon,
            color: enabled ? NubeRushColors.primary : NubeRushColors.disabled,
          ),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: titleColor,
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
          if (enabled)
            const Icon(Icons.chevron_right, color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }
}

class _MessageView extends StatelessWidget {
  const _MessageView({
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
                key: const Key('driver-home-retry'),
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
