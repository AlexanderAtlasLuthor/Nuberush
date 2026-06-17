// NubeRush Driver — root application widget.
//
// Hosts the MaterialApp shell. The default home is `DriverHomeBootstrap`
// (read-only Driver Home, Dr.1.3.E). Tests inject a pre-built [home] widget so
// they never go through bootstrap or touch real config/network.

import 'package:flutter/material.dart';

import 'providers.dart';
import 'router.dart';

/// Display name used across the app shell. Matches the locked native display
/// name `NubeRush Driver` (CFBundleDisplayName / android:label).
const String kAppTitle = 'NubeRush Driver';

class NubeRushDriverApp extends StatelessWidget {
  const NubeRushDriverApp({super.key, this.home});

  /// Injectable home surface. When null, the live [DriverHomeBootstrap] is used.
  final Widget? home;

  @override
  Widget build(BuildContext context) {
    // AppProviders is a placeholder boundary; in later subphases it will host
    // the auth/session and API client providers. For now it is a pass-through.
    return AppProviders(
      child: MaterialApp(
        title: kAppTitle,
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
          useMaterial3: true,
        ),
        home: home ?? const DriverHomeBootstrap(),
      ),
    );
  }
}
