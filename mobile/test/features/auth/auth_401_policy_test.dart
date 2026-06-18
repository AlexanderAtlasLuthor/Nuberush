// NubeRush Driver — end-to-end 401/403 auth policy through the shell (Dr.1.4.F).
//
// Wires a real ApiClient (MockClient transport) + ApiDriverRepository into the
// AuthGate, exactly like the runtime composition, and proves:
//   - 401 from a driver request signs out → AuthGate returns to LoginScreen.
//   - 403 keeps the user authenticated (no sign-out).
//   - the authenticated shell uses the live token-wired repository path.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nuberush_driver/core/api/api_client.dart';
import 'package:nuberush_driver/core/api/api_config.dart';
import 'package:nuberush_driver/core/auth/auth_controller.dart';
import 'package:nuberush_driver/core/auth/auth_session.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';
import 'package:nuberush_driver/features/auth/presentation/auth_gate.dart';
import 'package:nuberush_driver/features/auth/presentation/login_screen.dart';
import 'package:nuberush_driver/features/auth/presentation/logout_button.dart';
import 'package:nuberush_driver/features/driver/data/driver_repository.dart';

import '../../core/auth/auth_controller_test.dart' show FakeAuthActions;

final _config = ApiConfig.fromBaseUrl('https://api.example.com');
const _jsonHeaders = {'content-type': 'application/json'};

/// AuthSession fake whose signOut emits unauthenticated on the stream, exactly
/// like the real Supabase-backed session.
class EmittingAuthSession implements AuthSession {
  EmittingAuthSession(this._token);

  String? _token;
  int signOutCount = 0;
  final StreamController<AuthSessionState> _controller =
      StreamController<AuthSessionState>.broadcast();

  @override
  Future<String?> getAccessToken() async => _token;

  @override
  Stream<AuthSessionState> get authStateChanges => _controller.stream;

  @override
  Future<void> signOut() async {
    signOutCount++;
    _token = null;
    _controller.add(AuthSessionState.unauthenticated);
  }
}

Widget _host(Widget child) =>
    MaterialApp(theme: NubeRushTheme.dark(), home: child);

ApiDriverRepository _repoReturning(int status, EmittingAuthSession session) {
  final mock = MockClient((req) async {
    return http.Response(jsonEncode({'detail': 'x'}), status,
        headers: _jsonHeaders);
  });
  final client = ApiClient(
    config: _config,
    httpClient: mock,
    accessTokenProvider: () async => session.getAccessToken(),
    onUnauthorized: session.signOut,
  );
  return ApiDriverRepository(client);
}

void main() {
  testWidgets('401 from a driver request signs out and returns to LoginScreen',
      (tester) async {
    final session = EmittingAuthSession('tok');
    final repo = _repoReturning(401, session);

    await tester.pumpWidget(_host(AuthGate(
      session: session,
      controller: AuthController(FakeAuthActions()),
      repository: repo,
    )));
    await tester.pumpAndSettle();

    expect(session.signOutCount, greaterThanOrEqualTo(1));
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(LogoutButton), findsNothing);
  });

  testWidgets('403 keeps the user authenticated (no sign-out)', (tester) async {
    final session = EmittingAuthSession('tok');
    final repo = _repoReturning(403, session);

    await tester.pumpWidget(_host(AuthGate(
      session: session,
      controller: AuthController(FakeAuthActions()),
      repository: repo,
    )));
    await tester.pumpAndSettle();

    expect(session.signOutCount, 0);
    expect(find.byType(LoginScreen), findsNothing);
    // Still in the authenticated shell (logout affordance present).
    expect(find.byType(LogoutButton), findsOneWidget);
  });

  testWidgets('authenticated shell uses the live token-wired repository path',
      (tester) async {
    // A 200 path that captures the Authorization header proves the live
    // ApiClient (with the session token provider) is what the shell drives.
    final captured = <http.Request>[];
    final mock = MockClient((req) async {
      captured.add(req);
      // Minimal valid bodies for /driver/me and /driver/eligibility.
      if (req.url.path.endsWith('/driver/me')) {
        return http.Response(
          jsonEncode({
            'id': 'd-1',
            'user_id': 'u-1',
            'store_id': 's-1',
            'status': 'active',
            'approval_status': 'approved',
          }),
          200,
          headers: _jsonHeaders,
        );
      }
      return http.Response(
        jsonEncode({'can_go_online': true, 'blockers': [], 'user_active': true}),
        200,
        headers: _jsonHeaders,
      );
    });
    final session = EmittingAuthSession('live-token');
    final client = ApiClient(
      config: _config,
      httpClient: mock,
      accessTokenProvider: () async => session.getAccessToken(),
      onUnauthorized: session.signOut,
    );
    final repo = ApiDriverRepository(client);

    await tester.pumpWidget(_host(AuthGate(
      session: session,
      controller: AuthController(FakeAuthActions()),
      repository: repo,
    )));
    await tester.pumpAndSettle();

    expect(captured, isNotEmpty);
    expect(
      captured.every((r) => r.headers['Authorization'] == 'Bearer live-token'),
      isTrue,
    );
    expect(find.byType(LoginScreen), findsNothing);
  });
}
