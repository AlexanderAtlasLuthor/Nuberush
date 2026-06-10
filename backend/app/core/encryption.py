"""Symmetric encryption for accounting OAuth tokens at rest (F2.27.9.A).

QuickBooks OAuth access/refresh tokens are long-lived bearer credentials to a
merchant's accounting system, so they must NEVER be persisted in plaintext.
This module is the single chokepoint that encrypts a token before it touches
the database and decrypts it on read, using `cryptography.fernet.Fernet`
(AES-128-CBC + HMAC, authenticated). `cryptography` is already a backend
dependency (see backend/requirements.txt), so no new package is added.

The Fernet key comes from the SERVER-ONLY `QUICKBOOKS_TOKEN_ENCRYPTION_KEY`
via `get_quickbooks_settings()` — never exposed to the frontend, never logged.
A missing or malformed key raises `TokenEncryptionError`, a controlled failure
whose message NEVER contains the plaintext, the ciphertext, or the key.

This subphase ships the helper only: no OAuth flow, client, or sync writes a
token yet. There is deliberately NO logging in this module — tokens and keys
must never reach a log line.
"""
from __future__ import annotations

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from app.core.config import get_quickbooks_settings


class TokenEncryptionError(RuntimeError):
    """Raised when token encryption/decryption cannot proceed safely.

    The message is deliberately generic: it never echoes the plaintext, the
    ciphertext, or the encryption key, so a leaked stack trace or log line can
    never expose secret material.
    """


def _build_fernet() -> Fernet:
    """Construct a Fernet from the configured key, or fail safely.

    Reads the SERVER-ONLY `QUICKBOOKS_TOKEN_ENCRYPTION_KEY`. Raises
    `TokenEncryptionError` (without ever logging or echoing the key) when the
    key is missing or is not a valid 32-byte url-safe base64 Fernet key.
    """
    key = get_quickbooks_settings().quickbooks_token_encryption_key.strip()
    if not key:
        raise TokenEncryptionError(
            "QUICKBOOKS_TOKEN_ENCRYPTION_KEY is not configured."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        # Never include the key value in the message or chained context.
        raise TokenEncryptionError(
            "QUICKBOOKS_TOKEN_ENCRYPTION_KEY is not a valid Fernet key."
        ) from None


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string, returning url-safe base64 ciphertext.

    The returned ciphertext always differs from the input and round-trips via
    `decrypt_token`. Raises `TokenEncryptionError` on a missing/invalid key;
    the exception never contains the plaintext.
    """
    if not isinstance(plaintext, str):
        raise TokenEncryptionError("Token to encrypt must be a string.")
    fernet = _build_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt ciphertext produced by `encrypt_token`.

    Raises `TokenEncryptionError` on a missing/invalid key or on tampered /
    foreign ciphertext. The exception never contains the ciphertext or the key.
    """
    if not isinstance(ciphertext, str):
        raise TokenEncryptionError("Ciphertext to decrypt must be a string.")
    fernet = _build_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        raise TokenEncryptionError("Token decryption failed.") from None
