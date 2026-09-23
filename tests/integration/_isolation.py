"""One reset strategy for the whole Postgres integration lane (KCH-230).

WHY THIS EXISTS
Every module in this lane reset the database its own way, and the ways were
written at different times against different numbers of migrations:

* ``test_migration_0001_orgs_users`` dropped ``users``, ``orgs`` and
  ``schema_migrations`` -- the three tables that existed when 0001 was the
  newest migration.
* ``test_seed_service_account`` dropped the same three.
* ``test_migration_0003`` / ``0004`` / ``0005`` each carried their own
  hand-maintained list of table names.
* ``test_migration_0002`` recreated an isolated schema, which is the only
  approach that does not go stale.

``apply_pending`` applies **all** migrations, not the ones a given module is
about. So as 0005 added ``proposed_mutations`` and ``agent_turns``, every
module whose drop list predated it started leaving those tables behind, and
the next module's ``apply_pending`` hit::

    asyncpg.exceptions.DuplicateTableError:
        relation "proposed_mutations" already exists

That is not a flake -- it is the lane failing to isolate, and it fails
deterministically once more than one module runs. It went unnoticed because
no CI job has ever run this directory.

THE FIX IS THE PATTERN THAT WAS ALREADY HERE
``test_migration_0002`` already explained it in a comment: "Recreating the
schema (rather than dropping tables by name) also picks up any table a
future migration adds without this list needing to know about it." This
module is that comment, made shared, so migration 0006 cannot break the lane
by existing.

It also bounds the blast radius. The developer database may live in a
container shared with another product, so everything here happens inside a
dedicated schema that this lane owns and is free to drop; nothing touches
``public`` or any other database.
"""

from __future__ import annotations

import os
from typing import Any

# The schema this lane owns outright. Anything in it is disposable; nothing
# outside it is ever dropped.
TEST_SCHEMA = "finhive_integration"

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


async def reset_to_clean_schema(conn: Any, schema: str = TEST_SCHEMA) -> None:
    """Drop and recreate `schema`, then point this connection at it.

    Call this before `apply_pending`. Every table the migrations create
    lands inside `schema`, including `schema_migrations`, so the ledger is
    reset with the tables and the chain always applies from zero.

    Deliberately NOT a list of table names: a list has to be updated by
    whoever adds the next migration, and the failure mode when they forget
    is a confusing DuplicateTableError in an unrelated module rather than
    anything pointing at the omission.
    """
    await conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    await conn.execute(f"CREATE SCHEMA {schema}")
    await conn.execute(f"SET search_path TO {schema}")
