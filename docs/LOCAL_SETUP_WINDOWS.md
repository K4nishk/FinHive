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
   to that Supabase branch instead; otherwise it runs `supabase start` to spin
   up local Postgres + Auth.
5. Applies migrations and seeds the service account, once those exist
   (KCH-91, KCH-92) — before they land, the script prints a notice and skips
   these steps rather than failing.
6. Starts the API on `http://localhost:8000` (in a separate console window)
   and the SPA on `http://localhost:5173`. The SPA dev server proxies `/api`
   requests to the API port (see `web\vite.config.ts`). The API step is
   skipped with a notice until the FastAPI app is scaffolded (KCH-93).

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

M1a is being built incrementally. Until the corresponding issues land, the
script's migration, seed, and API steps are no-ops with a printed notice:

| Step | Lands in |
|---|---|
| Migration runner | KCH-91 |
| Service account seed | KCH-92 |
| FastAPI app (`finhive.dev_server:app`) | KCH-93 |

Once those merge, re-running `run_local_windows.bat` picks them up
automatically — no changes to this script or guide are needed.

## Troubleshooting

- **`ERROR: Python 3.10 or higher is required`** — install a supported Python
  version and make sure it's on `PATH` (`python --version`).
- **`ERROR: Node.js 20 or higher is required`** — install Node 20+
  (`node --version` to check).
- **`no DATABASE_URL is set and the Supabase CLI was not found`** — install
  the Supabase CLI, or set `DATABASE_URL` in `ops\.env.local`.
- **Port already in use** — another process is bound to `8000` or `5173`;
  stop it or edit the port in `run_local_windows.bat` / `web\vite.config.ts`.
- **Script won't run / execution policy errors** — `run_local_windows.bat` is
  a batch file, not a PowerShell script; run it from `cmd.exe` (or
  double-click it in Explorer), not `powershell.exe -File`.
