// NubeRush Driver — app home composition root + read-only navigation
// (Dr.1.3.E/F).
//
// `DriverHomeBootstrap` is the default home: it builds the core API client +
// read-only repository and the Driver Home, and wires simple Navigator pushes
// to the read-only assignment list and detail. If the public runtime config is
// missing/invalid it shows a safe "configuration required" state instead of
// crashing (and makes no network call). Widget tests inject pre-built
// screens/controllers instead of going through bootstrap.

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../core/api/api_client.dart';
import '../core/api/api_config.dart';
import '../features/driver/data/driver_repository.dart';
import '../features/driver/domain/driver_assignment.dart';
import '../features/driver/presentation/assignment_detail_controller.dart';
import '../features/driver/presentation/assignment_detail_screen.dart';
import '../features/driver/presentation/assignment_list_controller.dart';
import '../features/driver/presentation/assignment_list_screen.dart';
import '../features/driver/presentation/driver_home_controller.dart';
import '../features/driver/presentation/driver_home_screen.dart';
import 'app.dart';

class DriverHomeBootstrap extends StatefulWidget {
  const DriverHomeBootstrap({super.key});

  @override
  State<DriverHomeBootstrap> createState() => _DriverHomeBootstrapState();
}

class _DriverHomeBootstrapState extends State<DriverHomeBootstrap> {
  DriverHomeController? _homeController;
  DriverReadRepository? _repository;
  http.Client? _httpClient;
  String? _configError;

  @override
  void initState() {
    super.initState();
    try {
      final config = ApiConfig.fromEnvironment();
      final client = http.Client();
      _httpClient = client;
      final repository =
          ApiDriverRepository(ApiClient(config: config, httpClient: client));
      _repository = repository;
      _homeController = DriverHomeController(repository);
    } on ApiConfigError catch (error) {
      _configError = error.message;
    }
  }

  @override
  void dispose() {
    _homeController?.dispose();
    _httpClient?.close();
    super.dispose();
  }

  void _openAssignments(BuildContext context) {
    final repository = _repository;
    if (repository == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _DisposingScreen(
          controller: AssignmentListController(repository),
          builder: (controller) => AssignmentListScreen(
            controller: controller,
            onOpenAssignment: (ctx, assignment) =>
                _openAssignmentDetail(ctx, repository, assignment),
          ),
        ),
      ),
    );
  }

  void _openAssignmentDetail(
    BuildContext context,
    DriverReadRepository repository,
    DriverAssignmentSummary assignment,
  ) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _DisposingScreen(
          controller: AssignmentDetailController(repository, assignment.id),
          builder: (controller) =>
              AssignmentDetailScreen(controller: controller),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = _homeController;
    if (controller == null) {
      return Scaffold(
        appBar: AppBar(title: const Text(kAppTitle)),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              'Configuration required.\n${_configError ?? ''}',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }
    return DriverHomeScreen(
      controller: controller,
      onViewAssignments: _openAssignments,
    );
  }
}

/// Owns a [ChangeNotifier] controller for the lifetime of a pushed route and
/// disposes it on pop. Keeps controller lifecycle tidy without a DI package.
class _DisposingScreen<T extends ChangeNotifier> extends StatefulWidget {
  const _DisposingScreen({required this.controller, required this.builder});

  final T controller;
  final Widget Function(T controller) builder;

  @override
  State<_DisposingScreen<T>> createState() => _DisposingScreenState<T>();
}

class _DisposingScreenState<T extends ChangeNotifier>
    extends State<_DisposingScreen<T>> {
  @override
  void dispose() {
    widget.controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.builder(widget.controller);
}
