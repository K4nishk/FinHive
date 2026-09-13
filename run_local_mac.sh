#!/bin/bash
# run_local_mac.sh — FinHive M1a local launcher (macOS/Linux). [KCH-90]
#
# Mirrors the MVP1 launcher conventions (src/Loan Manager/run_mac.sh): a
# readable version-check failure, a project-local .venv, quiet installs.
#
# KCH-90's acceptance criteria is "a clean machine reaches a working local
# app from a single command" — migrations, the service-account seed, and the
# API all have to actually run for that to be true. Their infrastructure
# lands in separate tickets (migration runner: KCH-91, service-account seed:
# KCH-94, FastAPI app: KCH-102). Until all three exist, this script FAILS
# rather than silently launching an SPA-only app and calling it done. Pass
# --allow-partial (or set ALLOW_PARTIAL_SETUP=1) to opt into that partial
# run anyway for frontend-only work — see docs/LOCAL_SETUP_MACOS.md.
set -e

ALLOW_PARTIAL="${ALLOW_PARTIAL_SETUP:-0}"
for arg in "$@"; do
    if [ "$arg" = "--allow-partial" ]; then
        ALLOW_PARTIAL=1
    fi
done

echo "=== FinHive — macOS/Linux Local Setup ==="

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# --- Python version check (3.10 minimum, mirrors MVP1) ---
PYTHON_CMD=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.10 or higher is required but was not found."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi
echo "Using: $($PYTHON_CMD --version)"

# --- Node version check (20 minimum, matches .github/workflows/ci.yml) ---
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js 20 or higher is required but was not found."
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi
NODE_MAJOR=$(node -e "console.log(process.versions.node.split('.')[0])")
if [ "$NODE_MAJOR" -lt 20 ]; then
    echo "ERROR: Node.js 20 or higher is required (found $(node --version))."
    echo "Please install Node.js 20+ from https://nodejs.org/"
    exit 1
fi
echo "Using: Node $(node --version)"

# --- Python virtual environment ---
VENV_DIR="$ROOT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
    if ! "$VENV_DIR/bin/python" -c \
        'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
        echo "ERROR: .venv does not contain Python 3.10 or higher."
        echo "Remove .venv and run this script again."
        exit 1
    fi
else
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing backend dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"

echo "Installing frontend dependencies..."
(cd "$ROOT_DIR/web" && npm install --silent)

# --- Detect which stages have landed (before touching the database) ---
MISSING_STAGES=()
MIGRATE_AVAILABLE=0
SEED_AVAILABLE=0
DEV_SERVER_AVAILABLE=0

_spec() { "$PYTHON_CMD" -c \
  "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('$1') else 1)" \
  2>/dev/null; }

if _spec finhive.db.migrate; then
    MIGRATE_AVAILABLE=1
else
    MISSING_STAGES+=("migration runner (KCH-91)")
fi

if _spec finhive.db.seed_service_account; then
    SEED_AVAILABLE=1
else
    MISSING_STAGES+=("service account seed (KCH-94)")
fi

if _spec finhive.dev_server; then
    DEV_SERVER_AVAILABLE=1
else
    MISSING_STAGES+=("backend API (KCH-102)")
fi

if [ "${#MISSING_STAGES[@]}" -gt 0 ]; then
    if [ "$ALLOW_PARTIAL" != "1" ]; then
        echo "ERROR: KCH-90 is not fully satisfiable yet — missing:"
        for stage in "${MISSING_STAGES[@]}"; do
            echo "  - $stage"
        done
        echo "This is a partial environment, not a working local app."
        echo "Re-run once those land, or pass --allow-partial (or"
        echo "ALLOW_PARTIAL_SETUP=1) to launch the SPA-only subset."
        exit 1
    fi
    echo "WARNING: PARTIAL SETUP — proceeding without:"
    for stage in "${MISSING_STAGES[@]}"; do
        echo "  - $stage"
    done
fi

# --- Database: only required when a DB-dependent stage will run ---
NEEDS_DB=0
[ "$MIGRATE_AVAILABLE" = "1" ] && NEEDS_DB=1
[ "$SEED_AVAILABLE" = "1" ] && NEEDS_DB=1
[ "$DEV_SERVER_AVAILABLE" = "1" ] && NEEDS_DB=1

if [ "$NEEDS_DB" = "1" ]; then
    if [ -f "$ROOT_DIR/ops/.env.local" ]; then
        set -a
        # shellcheck disable=SC1091
        source "$ROOT_DIR/ops/.env.local"
        set +a
    fi

    if [ -n "${DATABASE_URL:-}" ]; then
        echo "DATABASE_URL is set — using the configured Supabase branch."
    elif command -v supabase &>/dev/null; then
        if ! docker info &>/dev/null; then
            echo "ERROR: Supabase CLI needs a running Docker runtime."
            echo "Start Docker Desktop and retry, or set DATABASE_URL"
            echo "in ops/.env.local to point at a Supabase branch."
            exit 1
        fi
        echo "Starting local Supabase (Postgres + Auth)..."
        supabase start
        export DATABASE_URL="postgresql://postgres:postgres@localhost:54322/postgres"
    else
        echo "ERROR: no DATABASE_URL and no Supabase CLI found."
        echo "Install it (brew install supabase/tap/supabase) to run"
        echo "Postgres locally, or set DATABASE_URL in ops/.env.local."
        exit 1
    fi
fi

# --- Run landed stages ---
if [ "$MIGRATE_AVAILABLE" = "1" ]; then
    echo "Applying migrations..."
    python -m finhive.db.migrate
fi

if [ "$SEED_AVAILABLE" = "1" ]; then
    echo "Seeding service account..."
    python -m finhive.db.seed_service_account
fi

# --- Launch API and SPA together ---
API_PID=""
cleanup() {
    [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null
    true
}
trap cleanup EXIT

_port_is_open() {
    "$PYTHON_CMD" -c "
import socket, sys
s = socket.socket()
s.settimeout(1)
sys.exit(0 if s.connect_ex(('127.0.0.1', $1)) == 0 else 1)
" 2>/dev/null
}

if [ "$DEV_SERVER_AVAILABLE" = "1" ] && [ "${#MISSING_STAGES[@]}" -eq 0 ]; then
    if _port_is_open 8000; then
        echo "ERROR: port 8000 is already in use by another process."
        echo "Stop whatever is listening on 8000 and re-run — otherwise the"
        echo "readiness check below could mistake it for this run's API."
        exit 1
    fi

    echo "Starting API on http://localhost:8000 ..."
    uvicorn finhive.dev_server:app --reload --port 8000 &
    API_PID=$!

    echo "Waiting for the API to become ready..."
    API_READY=0
    for _ in $(seq 1 30); do
        if ! kill -0 "$API_PID" 2>/dev/null; then
            echo "ERROR: the API process exited before becoming ready."
            break
        fi
        if _port_is_open 8000; then
            API_READY=1
            break
        fi
        sleep 1
    done
    if [ "$API_READY" != "1" ]; then
        echo "ERROR: the API did not become ready on http://localhost:8000 within 30s."
        exit 1
    fi
    echo "API is ready."
else
    echo "Starting the SPA only — the backend API is not part of this run."
fi

echo "Starting SPA on http://localhost:5173 ..."
(cd "$ROOT_DIR/web" && npm run dev)
