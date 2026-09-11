# Local Setup — Windows

One command brings up the FinHive web app locally: backend, frontend, and a
local database.

## Prerequisites

- **Python 3.10+** (3.13+ recommended) — https://www.python.org/downloads/
- **Node.js 20+** — https://nodejs.org/
- **Supabase CLI** (optional but recommended) — https://supabase.com/docs/guides/cli.
  Provides local Postgres + Auth via `supabase start`. If you'd rather point at a
  hosted Supabase branch instead of running Postgres locally, skip this and set
  `DATABASE_URL` as described below.
- **A Docker API-compatible container runtime** (e.g. Docker Desktop) —
  required if you use the Supabase CLI path above; `supabase start` runs
  Postgres and Auth as containers and fails without a running runtime. The
  script checks for a running runtime before calling `supabase start` and
  fails with a readable error if none is found. Not needed if you set
  `DATABASE_URL` to point at a hosted Supabase branch instead.

## Run it

```bat
run_local_windows.bat
```

The script:

1. Checks the Python and Node versions and fails with a readable message if
   either is missing or too old.
2. Creates `.venv` (if it doesn't already exist) and installs backend
   dependencies with `pip install -e ".[dev]"`.
3. Installs frontend dependencies with `npm install` in `web\`.
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
6. Starts the API on `http://localhost:8000` (in a separate console window)
   and the SPA on `http://localhost:5173`. The SPA dev server proxies `/api`
   requests to the API port (see `web\vite.config.ts`).

Close the API console window and press `Ctrl-C` in the main window to stop
the SPA dev server.

## Connecting to a Supabase branch instead of local Postgres

Add to `ops\.env.local` (gitignored — never commit credentials):

```bat
DATABASE_URL=postgresql://...supabase-branch-connection-string...
```

When `DATABASE_URL` is set, the script skips `supabase start` and uses that
connection directly.

## Current milestone state

M1a is being built incrementally. The script's migration, seed, and API
steps depend on infrastructure that hasn't landed yet:

| Step | Lands in |
|---|---|
| Migration runner | KCH-91 |
| Service account seed | KCH-94 |
| FastAPI app (`finhive.dev_server:app`) | KCH-102 |

Until all three exist, `run_local_windows.bat` fails with a list of what's
missing rather than launching an incomplete app — that partial state isn't
KCH-90's "working local app" acceptance criterion. Pass `--allow-partial`
(or set `ALLOW_PARTIAL_SETUP=1`) if you specifically want the SPA-only
subset anyway, e.g. for frontend-only work; the script prints a `PARTIAL
SETUP` warning naming what's missing rather than presenting it as success.
Once those three land, re-running `run_local_windows.bat` (no flag needed)
picks them up automatically.

## Troubleshooting

- **`ERROR: Python 3.10 or higher is required`** — install a supported Python
  version and make sure it's on `PATH` (`python --version`).
- **`ERROR: Node.js 20 or higher is required`** — install Node 20+
  (`node --version` to check).
- **`no DATABASE_URL is set and the Supabase CLI was not found`** — install
  the Supabase CLI, or set `DATABASE_URL` in `ops\.env.local`.
- **`the Supabase CLI needs a running Docker-compatible container runtime`**
  — start Docker Desktop (or another Docker API-compatible runtime) and
  retry, or set `DATABASE_URL` in `ops\.env.local` instead.
- **`KCH-90 is not fully satisfiable yet`** — the migration runner,
  service-account seed, or API haven't landed. Pass `--allow-partial` for an
  SPA-only run, or wait for KCH-91/KCH-94/KCH-102.
- **Port already in use** — another process is bound to `8000` or `5173`;
  stop it or edit the port in `run_local_windows.bat` / `web\vite.config.ts`.
- **Script won't run / execution policy errors** — `run_local_windows.bat` is
  a batch file, not a PowerShell script; run it from `cmd.exe` (or
  double-click it in Explorer), not `powershell.exe -File`.
