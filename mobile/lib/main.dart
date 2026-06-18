// NubeRush Driver — application entry point.
//
// Dr.1.4.C: async runtime bootstrap validates the public RuntimeConfig and
// (only when valid) initializes Supabase BEFORE rendering; invalid config shows
// a safe ConfigRequired state with no Supabase init / no network call.
// Dr.1.4.E: on a valid bootstrap we compose the runtime auth shell (AuthGate)
// which restores the session and gates the driver screens behind login.
// ApiClient token wiring / 401 policy remain deferred to Dr.1.4.F.

import 'package:flutter/widgets.dart';

import 'app/app.dart';
import 'app/app_bootstrap.dart';
import 'app/auth_composition.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final AppBootstrapState bootstrap = await bootstrapApp();
  runApp(NubeRushDriverApp(
    bootstrap: bootstrap,
    authShell: bootstrap is AppBootstrapReady
        ? buildRuntimeAuthShell(bootstrap.config)
        : null,
  ));
}
