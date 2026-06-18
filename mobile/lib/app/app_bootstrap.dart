// NubeRush Driver — async app bootstrap (Dr.1.4.C).
//
// Resolves the public RuntimeConfig and initializes Supabase BEFORE the app
// renders. Bootstrap is the only place Supabase.initialize runs, and only ever
// with valid public config. If config is missing/invalid the app renders a
// safe ConfigRequired state and NO Supabase init / NO backend network occurs.
//
// This subphase wires Supabase init + config gating ONLY. Session restore,
// login, AuthGate and ApiClient token wiring are deliberately deferred to
// Dr.1.4.D–F.
//
// Testability: the config loader and the Supabase initializer are injectable
// seams, so tests exercise both paths without a real Supabase or real env.

import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/config/runtime_config.dart';

/// Loads (and validates) the runtime configuration. Defaults to the env loader.
typedef RuntimeConfigLoader = RuntimeConfig Function();

/// Initializes Supabase from a validated [RuntimeConfig]. Defaults to the real
/// Supabase.initialize; tests inject a fake to avoid a real client.
typedef SupabaseInitializer = Future<void> Function(RuntimeConfig config);

/// Outcome of [bootstrapApp]: either ready (config valid + Supabase init'd) or
/// a safe config failure carrying only the offending variable names.
sealed class AppBootstrapState {
  const AppBootstrapState();
}

/// Config is valid and Supabase has been initialized.
class AppBootstrapReady extends AppBootstrapState {
  const AppBootstrapReady(this.config);

  final RuntimeConfig config;
}

/// Config is missing/invalid. Carries variable NAMES only (no values/secrets).
class AppBootstrapConfigFailure extends AppBootstrapState {
  const AppBootstrapConfigFailure(this.invalidVariables);

  final List<String> invalidVariables;
}

/// Default Supabase initializer — runs only with a valid [RuntimeConfig].
Future<void> defaultSupabaseInitializer(RuntimeConfig config) async {
  await Supabase.initialize(
    url: config.supabaseConfig.url.toString(),
    // The contract pins the PUBLIC anon key (NUBERUSH_SUPABASE_ANON_KEY).
    // supabase_flutter 2.15 soft-deprecates `anonKey` in favor of
    // `publishableKey`, but anon keys remain valid; keep anon key per contract.
    // ignore: deprecated_member_use
    anonKey: config.supabaseConfig.anonKey,
  );
}

/// Resolve config and (when valid) initialize Supabase.
///
/// Returns [AppBootstrapReady] on success or [AppBootstrapConfigFailure] when
/// config is missing/invalid. Never throws for a config problem; never calls
/// the Supabase initializer when config is invalid.
Future<AppBootstrapState> bootstrapApp({
  RuntimeConfigLoader configLoader = RuntimeConfig.fromEnvironment,
  SupabaseInitializer supabaseInitializer = defaultSupabaseInitializer,
}) async {
  final RuntimeConfig config;
  try {
    config = configLoader();
  } on RuntimeConfigError catch (error) {
    return AppBootstrapConfigFailure(error.invalidVariables);
  }

  await supabaseInitializer(config);
  return AppBootstrapReady(config);
}
