"""finhive/db/seed_service_account.py -- MVP1 owner service account seed (KCH-94).

Covers the pure config-loading and idempotent seeding logic against fake
`Connection`/`AdminAuth` doubles -- no real Postgres or Supabase instance
needed, mirroring the test strategy already used for the migration runner
(finhive/db/migrations.py) and migration 0001.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from finhive.db.seed_service_account import (
    ConfigError,
    SeedConfig,
    load_config,
    seed_service_account,
)


class FakeConnection:
    """In-memory stand-in for the asyncpg connection this seed needs."""

    def __init__(self) -> None:
        self.orgs: dict[str, Any] = {}
        self.users: dict[Any, tuple[Any, str]] = {}
        self.executed: list[tuple[str, tuple]] = []

    async def fetchval(self, query: str, *args: Any) -> Any:
        if "SELECT id FROM orgs" in query:
            (name,) = args
            return self.orgs.get(name)
        if "INSERT INTO orgs" in query:
            (name,) = args
            org_id = uuid.uuid4()
            self.orgs[name] = org_id
            return org_id
        raise AssertionError(f"unexpected fetchval query: {query!r}")

    async def execute(self, query: str, *args: Any) -> Any:
        self.executed.append((query, args))
        if "INSERT INTO users" in query:
            user_id, org_id = args
            self.users[user_id] = (org_id, "owner")
        return "OK"


class FakeAdmin:
    """Stands in for AdminClient: always resolves to the same fixed user id."""

    def __init__(self, user_id: uuid.UUID) -> None:
        self._user_id = user_id
        self.calls = 0

    def create_or_get_user(self, email: str, password: str) -> str:
        self.calls += 1
        return str(self._user_id)


def _config(**overrides: Any) -> SeedConfig:
    base = dict(
        database_url="postgresql://localhost/finhive",
        supabase_url="http://127.0.0.1:54321",
        supabase_service_role_key="service-role-key",
        owner_email="owner@example.com",
        owner_password="hunter2",
    )
    base.update(overrides)
    return SeedConfig(**base)


def test_seed_creates_org_and_owner_on_first_run() -> None:
    conn = FakeConnection()
    admin = FakeAdmin(uuid.uuid4())
    config = _config()

    org_id, user_id = asyncio.run(seed_service_account(conn, admin, config))

    assert conn.orgs == {config.org_name: uuid.UUID(org_id)}
    assert conn.users[uuid.UUID(user_id)] == (uuid.UUID(org_id), "owner")


def test_seed_is_idempotent_across_repeated_runs() -> None:
    conn = FakeConnection()
    admin = FakeAdmin(uuid.uuid4())
    config = _config()

    first_org, first_user = asyncio.run(seed_service_account(conn, admin, config))
    second_org, second_user = asyncio.run(seed_service_account(conn, admin, config))

    assert first_org == second_org
    assert first_user == second_user
    assert len(conn.orgs) == 1
    assert len(conn.users) == 1
    assert admin.calls == 2


def test_seed_always_assigns_role_owner() -> None:
    conn = FakeConnection()
    admin = FakeAdmin(uuid.uuid4())

    _, user_id = asyncio.run(seed_service_account(conn, admin, _config()))

    assert conn.users[uuid.UUID(user_id)][1] == "owner"


def test_load_config_raises_on_missing_required_vars() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config(env={})

    message = str(exc_info.value)
    required = (
        "DATABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "MVP1_OWNER_EMAIL",
        "MVP1_OWNER_PASSWORD",
    )
    for name in required:
        assert name in message


def test_load_config_applies_defaults_for_optional_vars() -> None:
    config = load_config(
        env={
            "DATABASE_URL": "postgresql://localhost/finhive",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "MVP1_OWNER_EMAIL": "owner@example.com",
            "MVP1_OWNER_PASSWORD": "hunter2",
        }
    )

    assert config.supabase_url == "http://127.0.0.1:54321"
    assert config.org_name == "MVP1 Owner"


def test_load_config_reads_all_provided_values() -> None:
    config = load_config(
        env={
            "DATABASE_URL": "postgresql://localhost/finhive",
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            "MVP1_OWNER_EMAIL": "owner@example.com",
            "MVP1_OWNER_PASSWORD": "hunter2",
            "MVP1_OWNER_ORG_NAME": "Acme Lending",
        }
    )

    assert config.supabase_url == "https://project.supabase.co"
    assert config.org_name == "Acme Lending"
