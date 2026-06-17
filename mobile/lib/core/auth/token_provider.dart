// NubeRush Driver — token provider bridge (Dr.1.3.D).
//
// Bridges [AuthSession] to the [AccessTokenProvider] the ApiClient expects, so
// the transport layer attaches `Authorization: Bearer <token>` from the live
// Supabase session without importing Supabase itself. Returns null when
// unauthenticated (never throws for that normal state). No token logging.

import '../api/api_client.dart' show AccessTokenProvider;

import 'auth_session.dart';

/// Build an [AccessTokenProvider] from an [AuthSession].
///
/// Pass the result into `ApiClient(accessTokenProvider: ...)`. A null/empty
/// token (unauthenticated) yields `null`, so the client omits Authorization.
AccessTokenProvider accessTokenProviderFor(AuthSession session) =>
    () => session.getAccessToken();
