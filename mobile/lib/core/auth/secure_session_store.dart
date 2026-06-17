// NubeRush Driver — secure session/token storage boundary (Dr.1.3.D).
//
// An app-owned interface over device secure storage so session/token handoff
// and future hardening never touch plain SharedPreferences. The Flutter
// implementation is backed by flutter_secure_storage:
//   - iOS:     Keychain
//   - Android: EncryptedSharedPreferences / Keystore-backed
//
// Token VALUES are never logged. Supabase manages its own session persistence
// internally; this boundary remains available for explicit secure token
// handoff and is the single place where any token is written at rest.

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Namespaced keys so NubeRush Driver values never collide with other data.
class SecureSessionKeys {
  const SecureSessionKeys._();

  static const String accessToken = 'nuberush.driver.auth.access_token';
  static const String refreshToken = 'nuberush.driver.auth.refresh_token';

  /// All keys this store owns — used by [SecureSessionStore.clear].
  static const List<String> all = <String>[accessToken, refreshToken];
}

/// Secure storage boundary for session tokens. Mockable for tests.
abstract class SecureSessionStore {
  Future<void> writeAccessToken(String token);
  Future<String?> readAccessToken();
  Future<void> deleteAccessToken();

  Future<void> writeRefreshToken(String token);
  Future<String?> readRefreshToken();
  Future<void> deleteRefreshToken();

  /// Remove every session value this store owns.
  Future<void> clear();
}

/// [SecureSessionStore] backed by flutter_secure_storage (Keychain/Keystore).
class FlutterSecureSessionStore implements SecureSessionStore {
  FlutterSecureSessionStore({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              // Android is Keystore-backed by default in v10+ (the old
              // encryptedSharedPreferences flag is deprecated/ignored).
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock_this_device,
              ),
            );

  final FlutterSecureStorage _storage;

  @override
  Future<void> writeAccessToken(String token) =>
      _storage.write(key: SecureSessionKeys.accessToken, value: token);

  @override
  Future<String?> readAccessToken() =>
      _storage.read(key: SecureSessionKeys.accessToken);

  @override
  Future<void> deleteAccessToken() =>
      _storage.delete(key: SecureSessionKeys.accessToken);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: SecureSessionKeys.refreshToken, value: token);

  @override
  Future<String?> readRefreshToken() =>
      _storage.read(key: SecureSessionKeys.refreshToken);

  @override
  Future<void> deleteRefreshToken() =>
      _storage.delete(key: SecureSessionKeys.refreshToken);

  @override
  Future<void> clear() async {
    for (final String key in SecureSessionKeys.all) {
      await _storage.delete(key: key);
    }
  }
}

/// In-memory [SecureSessionStore] for tests. Never used in production.
///
/// Lives in lib (not test/) so feature tests in later subphases can reuse it
/// without depending on platform secure-storage channels.
class InMemorySecureSessionStore implements SecureSessionStore {
  final Map<String, String> _values = <String, String>{};

  @override
  Future<void> writeAccessToken(String token) async =>
      _values[SecureSessionKeys.accessToken] = token;

  @override
  Future<String?> readAccessToken() async =>
      _values[SecureSessionKeys.accessToken];

  @override
  Future<void> deleteAccessToken() async =>
      _values.remove(SecureSessionKeys.accessToken);

  @override
  Future<void> writeRefreshToken(String token) async =>
      _values[SecureSessionKeys.refreshToken] = token;

  @override
  Future<String?> readRefreshToken() async =>
      _values[SecureSessionKeys.refreshToken];

  @override
  Future<void> deleteRefreshToken() async =>
      _values.remove(SecureSessionKeys.refreshToken);

  @override
  Future<void> clear() async => _values.clear();
}
