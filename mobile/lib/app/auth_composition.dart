// NubeRush Driver — runtime auth composition (Dr.1.4.E/F).
//
// Builds the real authenticated shell from the live Supabase client and wires
// the driver repository to an ApiClient that:
//   - attaches Authorization: Bearer <token> from the live session
//     (accessTokenProviderFor — never reads/stores raw tokens in widgets), and
//   - on a 401 fires the auth-expired handler (session.signOut) so the AuthGate
//     routes back to login. 401 is never auto-retried; 403 is left to surface as
//     a normalized ApiError (the user stays authenticated).
//
// Called ONLY from main() after a valid bootstrap (Supabase.initialize has run),
// so Supabase.instance is safe to touch here. Widget tests never call this; they
// inject fakes into AuthGate directly. Composition only — no business logic, no
// backend rules duplicated.

import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart' show Supabase;

import '../core/api/api_client.dart';
import '../core/auth/auth.dart';
import '../core/auth/auth_controller.dart';
import '../core/config/runtime_config.dart';
import '../features/auth/presentation/auth_gate.dart';
import '../features/driver/data/driver_repository.dart';

/// Construct the runtime [AuthGate] wired to the live Supabase auth client and
/// a token-authenticated driver repository.
Widget buildRuntimeAuthShell(RuntimeConfig config) {
  final auth = Supabase.instance.client.auth;
  final session = SupabaseAuthSession(
    gateway: GoTrueAuthGateway(auth),
    secureStore: FlutterSecureSessionStore(),
  );
  final controller = AuthController(
    SupabaseAuthActions(auth: auth, session: session),
  );

  final apiClient = ApiClient(
    config: config.apiConfig,
    httpClient: http.Client(),
    accessTokenProvider: accessTokenProviderFor(session),
    // 401 → sign out → AuthGate routes back to login. No auto-retry.
    onUnauthorized: session.signOut,
  );
  final repository = ApiDriverRepository(apiClient);

  return AuthGate(
    session: session,
    controller: controller,
    repository: repository,
  );
}
