// NubeRush Driver — root application widget.
//
// Hosts the MaterialApp shell. The home surface is chosen from the async
// [AppBootstrapState] (Dr.1.4.C) and the runtime auth shell (Dr.1.4.E):
//   - config invalid -> `ConfigRequiredScreen` (safe, branded)
//   - config valid   -> [authShell] (the AuthGate composed in main) when
//                       provided, else the legacy `DriverHomeBootstrap` path
// Tests inject a pre-built [home] widget so they never go through bootstrap or
// touch real config/network. No ApiClient token wiring / 401 policy yet
// (Dr.1.4.F).

import 'package:flutter/material.dart';

import '../core/theme/nuberush_theme.dart';
import '../features/auth/presentation/config_required_screen.dart';
import 'app_bootstrap.dart';
import 'providers.dart';
import 'router.dart';

/// Display name used across the app shell. Matches the locked native display
/// name `NubeRush Driver` (CFBundleDisplayName / android:label).
const String kAppTitle = 'NubeRush Driver';

class NubeRushDriverApp extends StatelessWidget {
  const NubeRushDriverApp({
    super.key,
    this.home,
    this.bootstrap,
    this.authShell,
  });

  /// Injectable home surface. When null, the home is derived from [bootstrap].
  final Widget? home;

  /// Result of the async startup bootstrap. When null (and [home] is null), the
  /// live [DriverHomeBootstrap] is used, preserving the prior default.
  final AppBootstrapState? bootstrap;

  /// Runtime authenticated shell (the AuthGate) composed in main() after a
  /// valid bootstrap. When null on a valid-config launch, the legacy
  /// [DriverHomeBootstrap] path is kept (used by tests that don't wire auth).
  final Widget? authShell;

  @override
  Widget build(BuildContext context) {
    // AppProviders is a placeholder boundary; in later subphases it will host
    // the auth/session and API client providers. For now it is a pass-through.
    return AppProviders(
      child: MaterialApp(
        title: kAppTitle,
        debugShowCheckedModeBanner: false,
        theme: NubeRushTheme.dark(),
        home: _resolveHome(),
      ),
    );
  }

  Widget _resolveHome() {
    if (home != null) return home!;
    final state = bootstrap;
    if (state is AppBootstrapConfigFailure) {
      return ConfigRequiredScreen(
        requiredVariables: state.invalidVariables.isEmpty
            ? null
            : state.invalidVariables,
      );
    }
    // Config valid: use the runtime auth shell (AuthGate) when composed; else
    // fall back to the legacy Driver Home path (tests that don't wire auth).
    if (authShell != null) return authShell!;
    return const DriverHomeBootstrap();
  }
}
