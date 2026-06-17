// NubeRush Driver — read-only Driver Home screen (Dr.1.3.E).
//
// Displays the backend-provided profile + eligibility. Shows loading, loaded,
// unauthenticated, error, and offline (with retry) states. It renders ONLY
// what /driver/me and /driver/eligibility return — no assignments, no action
// buttons, no compliance UI, no fake operational/earnings/route data.

import 'package:flutter/material.dart';

import '../domain/driver_eligibility.dart';
import '../domain/driver_profile.dart';
import 'driver_home_controller.dart';
import 'driver_home_state.dart';

const String kDriverHomeTitle = 'NubeRush Driver';

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({
    super.key,
    required this.controller,
    this.onViewAssignments,
  });

  final DriverHomeController controller;

  /// Optional read-only navigation to the assignments list (wired by the app
  /// shell). When null, no assignments entry is shown.
  final void Function(BuildContext context)? onViewAssignments;

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
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
    return Scaffold(
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
        ],
      ),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: widget.controller,
          builder: (context, _) => _body(context, widget.controller.state),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, DriverHomeState state) {
    switch (state.status) {
      case DriverHomeStatus.initial:
      case DriverHomeStatus.loading:
        return const Center(
          key: Key('driver-home-loading'),
          child: CircularProgressIndicator(),
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
        return _LoadedView(
          key: const Key('driver-home-loaded'),
          profile: state.profile,
          eligibility: state.eligibility,
        );
    }
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

class _LoadedView extends StatelessWidget {
  const _LoadedView({super.key, this.profile, this.eligibility});

  final DriverProfile? profile;
  final DriverEligibility? eligibility;

  @override
  Widget build(BuildContext context) {
    final profile = this.profile;
    final eligibility = this.eligibility;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (profile != null) _profileCard(context, profile),
        const SizedBox(height: 16),
        if (eligibility != null) _eligibilityCard(context, eligibility),
      ],
    );
  }

  Widget _profileCard(BuildContext context, DriverProfile profile) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Profile', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Status: ${profile.status}'),
            Text('Approval: ${profile.approvalStatus}'),
          ],
        ),
      ),
    );
  }

  Widget _eligibilityCard(BuildContext context, DriverEligibility eligibility) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Eligibility', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              eligibility.canGoOnline
                  ? 'You can go online.'
                  : 'You cannot go online yet.',
            ),
            if (eligibility.blockers.isNotEmpty) ...[
              const SizedBox(height: 8),
              for (final blocker in eligibility.blockers)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('• ${blocker.message}'),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
