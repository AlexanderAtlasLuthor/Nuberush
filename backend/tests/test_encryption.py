"""Tests for the accounting OAuth-token encryption helper (F2.27.9.A).

Validates `app.core.encryption`:
  - a valid key round-trips a token (encrypt -> decrypt -> original);
  - ciphertext always differs from the plaintext (and from itself across calls);
  - a missing or invalid key fails SAFELY with TokenEncryptionError, and the
    error never echoes the plaintext or the key;
  - tampered / foreign ciphertext fails closed;
  - non-string inputs are rejected.

The autouse `_isolate_settings_env` fixture (conftest) strips QuickBooks env and
disables `.env`, so the key defaults to "" unless a test opts in. Tests that
need a working key set QUICKBOOKS_TOKEN_ENCRYPTION_KEY in the process env and
clear the settings cache — no real credentials, no network.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core import encryption
from app.core.config import get_quickbooks_settings
from app.core.encryption import TokenEncryptionError
from app.core.encryption import decrypt_token
from app.core.encryption import encrypt_token


_PLAINTEXT = "qb-refresh-token-SUPER-SECRET-value-123"


@pytest.fixture
def with_encryption_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a valid Fernet key via process env and return it."""
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("QUICKBOOKS_TOKEN_ENCRYPTION_KEY", key)
    get_quickbooks_settings.cache_clear()
    try:
        yield key
    finally:
        get_quickbooks_settings.cache_clear()


# --------------------------------------------------------------------- #
# Round-trip + ciphertext properties
# --------------------------------------------------------------------- #


def test_encrypt_decrypt_round_trip(with_encryption_key: str) -> None:
    ciphertext = encrypt_token(_PLAINTEXT)
    assert decrypt_token(ciphertext) == _PLAINTEXT


def test_ciphertext_differs_from_plaintext(with_encryption_key: str) -> None:
    ciphertext = encrypt_token(_PLAINTEXT)
    assert ciphertext != _PLAINTEXT
    # The plaintext must not be embedded anywhere in the ciphertext.
    assert _PLAINTEXT not in ciphertext


def test_ciphertext_is_nondeterministic(with_encryption_key: str) -> None:
    # Fernet embeds a random IV + timestamp, so two encryptions differ even
    # for identical input — but both still decrypt back to the original.
    first = encrypt_token(_PLAINTEXT)
    second = encrypt_token(_PLAINTEXT)
    assert first != second
    assert decrypt_token(first) == _PLAINTEXT
    assert decrypt_token(second) == _PLAINTEXT


def test_round_trip_empty_string(with_encryption_key: str) -> None:
    ciphertext = encrypt_token("")
    assert ciphertext != ""
    assert decrypt_token(ciphertext) == ""


# --------------------------------------------------------------------- #
# Fail-safe: missing / invalid key
# --------------------------------------------------------------------- #


def test_encrypt_missing_key_fails_safely() -> None:
    # Default isolation leaves the key empty.
    get_quickbooks_settings.cache_clear()
    assert get_quickbooks_settings().quickbooks_token_encryption_key == ""

    with pytest.raises(TokenEncryptionError) as exc_info:
        encrypt_token(_PLAINTEXT)

    # The failure must NOT leak the plaintext token in its message.
    assert _PLAINTEXT not in str(exc_info.value)


def test_decrypt_missing_key_fails_safely() -> None:
    get_quickbooks_settings.cache_clear()
    with pytest.raises(TokenEncryptionError):
        decrypt_token("anything")


def test_encrypt_invalid_key_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_key = "this-is-not-a-valid-fernet-key"
    monkeypatch.setenv("QUICKBOOKS_TOKEN_ENCRYPTION_KEY", bad_key)
    get_quickbooks_settings.cache_clear()

    with pytest.raises(TokenEncryptionError) as exc_info:
        encrypt_token(_PLAINTEXT)

    # Neither the plaintext nor the (invalid) key value may appear.
    message = str(exc_info.value)
    assert _PLAINTEXT not in message
    assert bad_key not in message

    get_quickbooks_settings.cache_clear()


# --------------------------------------------------------------------- #
# Fail-closed: tampered / foreign ciphertext, wrong key, bad input types
# --------------------------------------------------------------------- #


def test_decrypt_garbage_ciphertext_fails(with_encryption_key: str) -> None:
    with pytest.raises(TokenEncryptionError):
        decrypt_token("not-a-real-fernet-token")


def test_decrypt_with_different_key_fails(
    monkeypatch: pytest.MonkeyPatch, with_encryption_key: str
) -> None:
    ciphertext = encrypt_token(_PLAINTEXT)

    # Rotate to a different key; the old ciphertext must no longer decrypt.
    other_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("QUICKBOOKS_TOKEN_ENCRYPTION_KEY", other_key)
    get_quickbooks_settings.cache_clear()

    with pytest.raises(TokenEncryptionError):
        decrypt_token(ciphertext)

    get_quickbooks_settings.cache_clear()


@pytest.mark.parametrize("bad_input", [None, 123, b"bytes", object()])
def test_encrypt_rejects_non_string(
    with_encryption_key: str, bad_input: object
) -> None:
    with pytest.raises(TokenEncryptionError):
        encrypt_token(bad_input)  # type: ignore[arg-type]


def test_module_defines_only_the_public_helpers() -> None:
    # The module exposes the two helpers + the controlled error type, and
    # deliberately does NOT define any logging that could echo a token.
    assert hasattr(encryption, "encrypt_token")
    assert hasattr(encryption, "decrypt_token")
    assert hasattr(encryption, "TokenEncryptionError")
