# Local Setup — macOS / Linux

One command brings up the FinHive web app locally: backend, frontend, and a
local database.

## Prerequisites

- **Python 3.10+** (3.13+ recommended) — https://www.python.org/downloads/
- **Node.js 20+** — https://nodejs.org/
- **Supabase CLI** (optional but recommended) — `brew install supabase/tap/supabase`.
  Provides local Postgres + Auth via `supabase start`. If you'd rather point at a
  hosted Supabase branch instead of running Postgres locally, skip this and set
  `DATABASE_URL` as described below.
- **A Docker API-compatible container runtime** (e.g. Docker Desktop, OrbStack,
  Colima) — required if you use the Supabase CLI path above; `supabase start`
  runs Postgres and Auth as containers and fails without a running runtime. The
  script checks `docker info` before calling `supabase start` and fails with a
  readable error if no runtime is running. Not needed if you set `DATABASE_URL`
  to point at a hosted Supabase branch instead.

## Run it

```bash
./run_local_mac.sh
```

The script:

1. Checks the Python and Node versions and fails with a readable message if
   either is missing or too old.
2. Creates `.venv` (if it doesn't already exist) and installs backend
   dependencies with `pip install -e ".[dev]"`.
3. Installs frontend dependencies with `npm install` in `web/`.
4. Starts a local database: if `DATABASE_URL` is set (see below), it connects
   to that Supabase branch instead; otherwise it checks that a container
   runtime is running and then runs `supabase start` to spin up local
   Postgres + Auth.
5. Applies migrations, seeds the service account, and starts the API — once
   those exist (KCH-91, KCH-94, KCH-102 respectively). **Until all three
   exist, the script fails instead of launching a partial app**, since a
   clean-machine run without them is not a working local app. Pass
   `--allow-partial` (or set `ALLOW_PARTIAL_SETUP=1`) to opt into an
   SPA-only run anyway, e.g. for frontend-only work.
   Seeding (KCH-94) needs the service-account credentials described below,
   in addition to `DATABASE_URL`.
6. Starts the API on `http://localhost:8000` and the SPA on
   `http://localhost:5173` together. The SPA dev server proxies `/api`
   requests to the API port (see `web/vite.config.ts`).

Stop everything with `Ctrl-C`; the script tears down the API process it
started.

## Connecting to a Supabase branch instead of local Postgres

Add to `ops/.env.local` (gitignored — never commit credentials):

```bash
export DATABASE_URL="postgresql://...supabase-branch-connection-string..."
```

When `DATABASE_URL` is set, the script skips `supabase start` and uses that
connection directly.

## Service account credentials (KCH-94)

Milestone one skips public signup: a single service account is seeded for
the existing MVP1 user, with `role=owner` and a real `org_id`, authenticating
against Supabase Auth. Add its credentials to `ops/.env.local` alongside
`DATABASE_URL`:

```bash
export SUPABASE_URL="http://127.0.0.1:54321"          # supabase start's default; omit to use it
export SUPABASE_SERVICE_ROLE_KEY="..."                 # printed by `supabase start`, or from a hosted project's API settings
export MVP1_OWNER_EMAIL="owner@example.com"
export MVP1_OWNER_PASSWORD="..."
```

`SUPABASE_SERVICE_ROLE_KEY` bypasses Row Level Security and is used in
exactly one place, `finhive/db/admin.py`, to provision the Supabase Auth user
this seed needs. Re-running `python -m finhive.db.seed_service_account` (or
`./run_local_mac.sh`) is idempotent: it looks the org and auth user up by
name/email before creating either.

## Encryption master key (KCH-97)

Every NPI column (`finhive/db/encryption.py`, `finhive/db/blind_index.py`)
needs a 32-byte master key, loaded by `finhive/db/keys.py`. Generate one and
add it to `ops/.env.local`:

```bash
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

```bash
export FINHIVE_KEY_VERSION=1
export FINHIVE_MASTER_KEY_V1="<base64 output from above>"
```

`FINHIVE_KEY_VERSION` names which `key_version` new writes are encrypted
under; `FINHIVE_MASTER_KEY_V<n>` supplies the master for version `n`. Keep an
old version's var set until every row has been rotated off it -- see
`docs/KEY_MANAGEMENT.md` for the rotation and backup/restore procedure. A
lost key means unrecoverable data: back the master key up before it is ever
used to encrypt real data.

## Current milestone state

M1a is being built incrementally. The script's migration and API steps
depend on infrastructure that hasn't landed yet:

| Step | Lands in |
|---|---|
| Migration runner | KCH-91 |
| Service account seed | KCH-94 — done |
| FastAPI app (`finhive.dev_server:app`) | KCH-102 |

Until all three exist, `./run_local_mac.sh` fails with a list of what's
missing rather than launching an incomplete app — that partial state isn't
KCH-90's "working local app" acceptance criterion. Pass `--allow-partial`
(or set `ALLOW_PARTIAL_SETUP=1`) if you specifically want the SPA-only
subset anyway, e.g. for frontend-only work; the script prints a `PARTIAL
SETUP` warning naming what's missing rather than presenting it as success.
Once those land, re-running `./run_local_mac.sh` (no flag needed) picks them
up automatically.

## Troubleshooting

- **`ERROR: Python 3.10 or higher is required`** — install a supported Python
  version and make sure it's on `PATH` (`python3 --version`).
- **`ERROR: Node.js 20 or higher is required`** — install Node 20+
  (`node --version` to check).
- **`no DATABASE_URL is set and the Supabase CLI was not found`** — install
  the Supabase CLI, or set `DATABASE_URL` in `ops/.env.local`.
- **`the Supabase CLI needs a running Docker-compatible container runtime`**
  — start Docker Desktop (or another Docker API-compatible runtime) and
  retry, or set `DATABASE_URL` in `ops/.env.local` instead.
- **`KCH-90 is not fully satisfiable yet`** — the migration runner,
  service-account seed, or API haven't landed. Pass `--allow-partial` for an
  SPA-only run, or wait for KCH-91/KCH-94/KCH-102.
- **Port already in use** — another process is bound to `8000` or `5173`;
  stop it or edit the port in `run_local_mac.sh` / `web/vite.config.ts`.
