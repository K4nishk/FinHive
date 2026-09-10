"""finhive/db/admin.py -- Supabase service-role Admin API client (KCH-94).

Exercises the request/response handling (create, duplicate-email fallback to
lookup, and error propagation) against an injected fake HTTP opener so no
network call or real Supabase instance is needed.
"""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from finhive.db.admin import AdminClient, SupabaseAdminError


class FakeOpener:
    """Replays a fixed sequence of responses/exceptions, one per call."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.requests: list = []

    def __call__(self, req):
        self.requests.append(req)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(json.dumps(response).encode("utf-8"))


def _duplicate_email_error() -> HTTPError:
    body = json.dumps({"code": "email_exists", "msg": "User already registered"}).encode()
    return HTTPError(
        "http://x/auth/v1/admin/users", 422, "Unprocessable Entity", None, io.BytesIO(body)
    )


def test_create_or_get_user_creates_new_user_when_none_exists() -> None:
    opener = FakeOpener([{"id": "new-user-id"}])
    client = AdminClient("http://127.0.0.1:54321", "service-role-key", opener=opener)

    user_id = client.create_or_get_user("owner@example.com", "hunter2")

    assert user_id == "new-user-id"
    assert len(opener.requests) == 1
    assert opener.requests[0].get_method() == "POST"
    assert opener.requests[0].get_header("Apikey") == "service-role-key"


def test_create_or_get_user_returns_existing_id_when_already_registered() -> None:
    opener = FakeOpener(
        [
            _duplicate_email_error(),
            {"users": [{"id": "existing-id", "email": "OWNER@example.com"}]},
        ]
    )
    client = AdminClient("http://127.0.0.1:54321", "service-role-key", opener=opener)

    user_id = client.create_or_get_user("owner@example.com", "hunter2")

    assert user_id == "existing-id"
    assert len(opener.requests) == 2
    assert opener.requests[1].get_method() == "GET"


def test_create_or_get_user_raises_when_duplicate_but_not_found_by_email() -> None:
    opener = FakeOpener([_duplicate_email_error(), {"users": []}])
    client = AdminClient("http://127.0.0.1:54321", "service-role-key", opener=opener)

    with pytest.raises(SupabaseAdminError, match="no matching user was found"):
        client.create_or_get_user("owner@example.com", "hunter2")


def test_create_or_get_user_raises_supabase_admin_error_on_unexpected_http_error() -> None:
    server_error = HTTPError(
        "http://x/auth/v1/admin/users", 500, "Internal Server Error", None, io.BytesIO(b"{}")
    )
    opener = FakeOpener([server_error])
    client = AdminClient("http://127.0.0.1:54321", "service-role-key", opener=opener)

    with pytest.raises(SupabaseAdminError, match="HTTP 500"):
        client.create_or_get_user("owner@example.com", "hunter2")
