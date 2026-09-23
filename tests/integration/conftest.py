"""Integration-lane guard: skip locally, but never skip silently in CI.

The TRAP in KCH-230 is that `mvp1-regression` runs whole test directories as
a required check, so these tests MUST skip rather than fail on a machine with
no Postgres -- otherwise every contributor goes red.

The inverse trap is worse and is what actually happened here. Migrations
0001-0005 shipped with three defects that this directory would have caught on
its first run: a foreign key into Supabase's `auth.users`, a reference to a
non-existent `organizations` table, and a UUID column keyed to a BIGINT
primary key. They survived because no CI job ran this directory, and a lane
that skips everything reports exactly the same green as a lane that passes.

So the skip is conditional on intent. Locally, absent `TEST_DATABASE_URL`,
these skip quietly. In CI the workflow sets `FINHIVE_REQUIRE_INTEGRATION=1`,
and then a missing database or a missing driver is a hard error at collection
rather than a silent pass -- a typo in the connection string cannot present
as success.
"""

from __future__ import annotations

import os

from tests.integration._isolation import DATABASE_URL

_REQUIRED = os.environ.get("FINHIVE_REQUIRE_INTEGRATION") not in (None, "", "0")


def _explain(problem: str) -> str:
    return (
        f"FINHIVE_REQUIRE_INTEGRATION is set, so the Postgres integration lane "
        f"must actually run -- but {problem}.\n\n"
        "This guard exists because a lane that skips everything is "
        "indistinguishable from a lane that passes, and three broken "
        "migrations shipped behind exactly that ambiguity (KCH-225).\n\n"
        "Either provide a database:\n"
        "    TEST_DATABASE_URL=postgresql://user@host:5432/dbname\n"
        "or unset FINHIVE_REQUIRE_INTEGRATION to allow skipping."
    )


if _REQUIRED:
    if not DATABASE_URL:
        raise RuntimeError(_explain("TEST_DATABASE_URL is not set"))
    try:
        import asyncpg  # noqa: F401
    except ImportError as exc:  # pragma: no cover - CI-config failure only
        raise RuntimeError(
            _explain("asyncpg is not installed (pip install -e '.[server]')")
        ) from exc
