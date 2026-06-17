// NubeRush Driver — read-only assignment list screen (Dr.1.3.F).
//
// Lists assignment summaries. Tapping a row may open the read-only detail via
// the injected [onOpenAssignment] callback (wired by the app shell). NO action
// buttons (accept/decline/start/...), no compliance UI, no fake map/earnings.

import 'package:flutter/material.dart';

import '../domain/driver_assignment.dart';
import 'assignment_list_controller.dart';
import 'assignment_list_state.dart';

class AssignmentListScreen extends StatefulWidget {
  const AssignmentListScreen({
    super.key,
    required this.controller,
    this.onOpenAssignment,
  });

  final AssignmentListController controller;
  final void Function(BuildContext context, DriverAssignmentSummary assignment)?
      onOpenAssignment;

  @override
  State<AssignmentListScreen> createState() => _AssignmentListScreenState();
}

class _AssignmentListScreenState extends State<AssignmentListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Assignments')),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: widget.controller,
          builder: (context, _) => _body(context, widget.controller.state),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, AssignmentListState state) {
    switch (state.status) {
      case AssignmentListStatus.initial:
      case AssignmentListStatus.loading:
        return const Center(
          key: Key('assignments-loading'),
          child: CircularProgressIndicator(),
        );
      case AssignmentListStatus.empty:
        return const _Message(
          key: Key('assignments-empty'),
          icon: Icons.inbox_outlined,
          message: 'No assignments yet.',
        );
      case AssignmentListStatus.unauthenticated:
        return const _Message(
          key: Key('assignments-unauthenticated'),
          icon: Icons.lock_outline,
          message: 'Please sign in to continue.',
        );
      case AssignmentListStatus.offline:
        return _Message(
          key: const Key('assignments-offline'),
          icon: Icons.wifi_off,
          message: state.errorMessage ?? 'Network unavailable.',
          onRetry: widget.controller.retry,
        );
      case AssignmentListStatus.error:
        return _Message(
          key: const Key('assignments-error'),
          icon: Icons.error_outline,
          message: state.errorMessage ?? 'Something went wrong.',
          onRetry: widget.controller.retry,
        );
      case AssignmentListStatus.loaded:
        return ListView.builder(
          key: const Key('assignments-loaded'),
          itemCount: state.assignments.length,
          itemBuilder: (context, index) {
            final a = state.assignments[index];
            return ListTile(
              key: Key('assignment-row-${a.id}'),
              title: Text(a.storeName ?? 'Order ${a.orderId}'),
              subtitle: Text('Status: ${a.status}'),
              trailing: const Icon(Icons.chevron_right),
              onTap: widget.onOpenAssignment == null
                  ? null
                  : () => widget.onOpenAssignment!(context, a),
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
                key: const Key('assignments-retry'),
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
