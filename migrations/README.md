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

It exits non-zero on any `MigrationError` (checksum mismatch, duplicate version
number), so wiring it into CI as a required step is a one-line addition once a
target database is available there.

Running it twice against the same database is a no-op the second time — nothing to
apply, nothing re-applied.
