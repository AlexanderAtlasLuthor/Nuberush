// NubeRush Driver — provider boundary placeholder.
//
// Dr.1.3.B skeleton: a pass-through wrapper that marks where app-wide
// providers (auth/session, API client, config) will be installed in later
// Dr.1.3 subphases. It introduces no state management dependency yet and no
// backend coupling.

import 'package:flutter/widgets.dart';

/// Placeholder app-wide provider boundary. Currently a no-op pass-through.
class AppProviders extends StatelessWidget {
  const AppProviders({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => child;
}
