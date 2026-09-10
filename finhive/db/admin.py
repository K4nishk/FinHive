"""Supabase service-role Admin API client (KCH-94).

Confines the `service_role` key to this one module (ARD v2.0.0 section 8, Gotcha 3):
`service_role` bypasses Row Level Security entirely, so every other layer in
this codebase talks to Postgres as the calling user's JWT, never as
`service_role`. The only legitimate use here is provisioning the Supabase
Auth user for the milestone-one service account -- it has no JWT of its own
yet, since it doesn't exist until this module creates it.

Talks to GoTrue's REST API directly over `urllib` rather than adding a
Supabase SDK dependency for one admin call. The HTTP transport is injectable
(`opener`) so tests exercise the real request/response handling without a
network call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

_USERS_PATH = "/auth/v1/admin/users"
_PER_PAGE = 200
_MAX_PAGES = 5  # local/dev instances only -- bounds the email lookup scan

Opener = Callable[[urlrequest.Request], Any]


class SupabaseAdminError(Exception):
    """A Supabase Admin API call failed unexpectedly."""


class AdminClient:
    """Thin wrapper over Supabase's GoTrue Admin REST API."""

    def __init__(
        self,
        base_url: str,
        service_role_key: str,
        opener: Opener = urlrequest.urlopen,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_role_key = service_role_key
        self._opener = opener

    def create_or_get_user(self, email: str, password: str) -> str:
        """Return the Supabase auth user id for `email`, creating it if needed."""
        created = self._try_create_user(email, password)
        if created is not None:
            return created

        found = self._find_user_by_email(email)
        if found is None:
            raise SupabaseAdminError(
                f"user {email!r} was reported as already registered, but no "
                "matching user was found while paging admin/users"
            )
        return found

    def _try_create_user(self, email: str, password: str) -> str | None:
        body = json.dumps(
            {"email": email, "password": password, "email_confirm": True}
        ).encode("utf-8")
        req = urlrequest.Request(
            self._base_url + _USERS_PATH,
            data=body,
            method="POST",
            headers=self._headers({"Content-Type": "application/json"}),
        )
        try:
            with self._opener(req) as resp:
                payload = json.load(resp)
        except urlerror.HTTPError as exc:
            if _looks_like_duplicate(exc):
                return None
            raise SupabaseAdminError(
                f"create user failed: HTTP {exc.code} {exc.reason}"
            ) from exc
        except urlerror.URLError as exc:
            raise SupabaseAdminError(
                f"could not reach Supabase Auth: {exc.reason}"
            ) from exc

        user_id = payload.get("id")
        if not user_id:
            raise SupabaseAdminError(f"create user response had no id: {payload!r}")
        return str(user_id)

    def _find_user_by_email(self, email: str) -> str | None:
        target = email.strip().lower()
        for page in range(1, _MAX_PAGES + 1):
            req = urlrequest.Request(
                f"{self._base_url}{_USERS_PATH}?page={page}&per_page={_PER_PAGE}",
                method="GET",
                headers=self._headers({}),
            )
            try:
                with self._opener(req) as resp:
                    payload = json.load(resp)
            except urlerror.HTTPError as exc:
                raise SupabaseAdminError(
                    f"list users failed: HTTP {exc.code} {exc.reason}"
                ) from exc
            except urlerror.URLError as exc:
                raise SupabaseAdminError(
                    f"could not reach Supabase Auth: {exc.reason}"
                ) from exc

            users = payload.get("users", payload) if isinstance(payload, dict) else payload
            for user in users:
                if str(user.get("email", "")).strip().lower() == target:
                    return str(user["id"])
            if len(users) < _PER_PAGE:
                return None
        return None

    def _headers(self, extra: dict[str, str]) -> dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            **extra,
        }


def _looks_like_duplicate(exc: urlerror.HTTPError) -> bool:
    if exc.code not in (400, 409, 422):
        return False
    try:
        payload = json.loads(exc.read())
    except (ValueError, OSError):
        return False
    code = str(payload.get("code", "")).lower()
    msg = str(payload.get("msg") or payload.get("message") or "").lower()
    return "already" in msg or "exists" in code or "exists" in msg
