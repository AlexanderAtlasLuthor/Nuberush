// Dr.1.3.D — SecureSessionStore tests. Uses the in-memory implementation so no
// platform secure-storage channel is required. No real tokens.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/auth/secure_session_store.dart';

void main() {
  late InMemorySecureSessionStore store;

  setUp(() => store = InMemorySecureSessionStore());

  test('writes and reads the access token', () async {
    await store.writeAccessToken('a-token');
    expect(await store.readAccessToken(), 'a-token');
  });

  test('deletes the access token', () async {
    await store.writeAccessToken('a-token');
    await store.deleteAccessToken();
    expect(await store.readAccessToken(), isNull);
  });

  test('writes and reads the refresh token', () async {
    await store.writeRefreshToken('r-token');
    expect(await store.readRefreshToken(), 'r-token');
    await store.deleteRefreshToken();
    expect(await store.readRefreshToken(), isNull);
  });

  test('clear removes all session values', () async {
    await store.writeAccessToken('a-token');
    await store.writeRefreshToken('r-token');
    await store.clear();
    expect(await store.readAccessToken(), isNull);
    expect(await store.readRefreshToken(), isNull);
  });

  test('keys are namespaced under nuberush.driver.auth', () {
    expect(SecureSessionKeys.accessToken, startsWith('nuberush.driver.auth.'));
    expect(SecureSessionKeys.refreshToken, startsWith('nuberush.driver.auth.'));
    expect(
      SecureSessionKeys.all,
      containsAll(
        <String>[SecureSessionKeys.accessToken, SecureSessionKeys.refreshToken],
      ),
    );
  });
}
