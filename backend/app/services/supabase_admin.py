"""Supabase Auth Admin API client for server-side user provisioning (F2.22.2.E).

`POST /auth/users` creates a Supabase `auth.users` record (the identity)
and the matching `public.users` row (the authorization data) in one
request. This module wraps the Supabase Auth Admin REST API for that
purpose.

Hard rules:

- The **service-role key is a server-only secret**. It is never logged,
  never placed in an exception message, and never returned in a response.
  Error messages here carry only an HTTP status code, no headers/body.
- This module performs **no RBAC**. Authorization — who may create whom,
  store scoping, the no-admin-creation rule — stays in the route and
  `app.core.permissions`. This wrapper is pure I/O.
- `user_metadata` written to `auth.users` is **informational only**.
  NubeRush authority (role, store_id, is_active) lives in `public.users`;
  nothing here or downstream may treat a Supabase metadata field as a
  permission. `app.core.supabase_auth` already discards all claims but
  `sub` for the same reason.

The Supabase Admin endpoints used:
  POST   {SUPABASE_URL}/auth/v1/admin/users
  DELETE {SUPABASE_URL}/auth/v1/admin/users/{id}
"""

from __future__ import annotations

import uuid

import httpx

from app.core.config import get_supabase_auth_settings


_ADMIN_USERS_PATH = "/auth/v1/admin/users"
_REQUEST_TIMEOUT_SECONDS = 10.0


class SupabaseAdminError(Exception):
    """Raised when a Supabase Admin API call fails.

    The message is intentionally coarse and secret-free (status code at
    most). The route maps it to a controlled 5xx.
    """


def _require_admin_config() -> tuple[str, str]:
    """Return (base_url, service_role_key) or raise if unconfigured."""
    settings = get_supabase_auth_settings()
    base = settings.supabase_url.strip().rstrip("/")
    key = settings.supabase_service_role_key.strip()
    if not base:
        raise SupabaseAdminError("SUPABASE_URL is not configured")
    if not key:
        raise SupabaseAdminError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured"
        )
    return base, key


def _admin_headers(service_role_key: str) -> dict[str, str]:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }


def create_auth_user(
    email: str,
    password: str,
    user_metadata: dict | None = None,
) -> uuid.UUID:
    """Create a Supabase `auth.users` record; return its UUID.

    The user is created pre-confirmed (`email_confirm: true`) because an
    administrator provisions it out of band. `user_metadata` is stored on
    `auth.users` for human/debug context only — never an authority source.

    Raises `SupabaseAdminError` on any transport error, non-2xx response,
    or unparseable body.
    """
    base, key = _require_admin_config()
    body: dict = {
        "email": email,
        "password": password,
        "email_confirm": True,
    }
    if user_metadata:
        body["user_metadata"] = user_metadata

    try:
        response = httpx.post(
            f"{base}{_ADMIN_USERS_PATH}",
            headers=_admin_headers(key),
            json=body,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        # Note: do not interpolate `exc` detail that could echo the URL
        # with query params; a bare message keeps secrets out of logs.
        raise SupabaseAdminError(
            "Supabase Admin API request failed during user create"
        ) from exc

    if response.status_code not in (200, 201):
        raise SupabaseAdminError(
            "Supabase Admin API returned status "
            f"{response.status_code} on user create"
        )

    try:
        data = response.json()
        return uuid.UUID(str(data["id"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise SupabaseAdminError(
            "Supabase Admin API returned an unexpected create response"
        ) from exc


def delete_auth_user(auth_user_id: uuid.UUID) -> None:
    """Delete a Supabase `auth.users` record.

    Used to roll back a half-created user when the `public.users` insert
    fails after the `auth.users` row was created — preventing an
    `auth.users` orphan with no `public.users` mapping.

    Raises `SupabaseAdminError` on transport error or non-2xx response.
    """
    base, key = _require_admin_config()
    try:
        response = httpx.delete(
            f"{base}{_ADMIN_USERS_PATH}/{auth_user_id}",
            headers=_admin_headers(key),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise SupabaseAdminError(
            "Supabase Admin API request failed during user delete"
        ) from exc

    if response.status_code not in (200, 204):
        raise SupabaseAdminError(
            "Supabase Admin API returned status "
            f"{response.status_code} on user delete"
        )
