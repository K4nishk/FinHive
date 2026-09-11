# Migrations

Forward-only, numbered SQL. No down-migrations — rolling back a schema on a live
database is more dangerous than rolling forward (ARD §9 "Migrations").

## Convention

```
migrations/
  0001_init_orgs_users.sql
  0002_loans_add_org_id.sql
  0003_rls_policies.sql
```

- Filename: `NNNN_name.sql` — a zero-padded 4-digit version, an underscore, then a
  lowercase `snake_case` name.
- Versions are applied in ascending numeric order.
- Once a migration has been applied, its file is immutable. Need a different
  schema? Add a new migration — never edit an applied one.

## How it's enforced

`finhive/db/migrations.py` is the runner. It tracks applied migrations in a
`schema_migrations` table (`version`, `name`, `checksum`, `applied_at`) and, before
applying anything, verifies that every already-applied file's current on-disk
checksum still matches the checksum recorded at apply time. A mismatch raises
`ChecksumMismatchError` and aborts before touching the database — this is what
makes editing an applied migration a hard failure instead of a silent drift.

Run it directly:

```bash
DATABASE_URL=postgres://... python -m finhive.db.migrations
```

`run_local_mac.sh` and `run_local_windows.bat` (KCH-90) already call it this way
against the local or branch database before starting the app, so migrations run
as part of every local dev bring-up.

It exits non-zero on any `MigrationError` (checksum mismatch, renamed or edited
file, out-of-order file, duplicate version number), so wiring it into CI as a
required step is a one-line addition once a target database -- e.g. an
ephemeral Supabase branch -- is available there. That CI wiring and an
automated dry-run against a Supabase branch are tracked separately; they need
CI-provisioned database credentials this repo doesn't have yet, which is
outside KCH-91's scope (build the runner) and acceptance criteria (idempotent
re-run, edited-migration failure -- both covered by the test suite in
`tests/unit/test_migrations_runner.py` and `tests/integration/test_migrations_lock.py`).

Running it twice against the same database is a no-op the second time — nothing to
apply, nothing re-applied.
