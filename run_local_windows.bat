@echo off
setlocal enabledelayedexpansion
:: run_local_windows.bat -- FinHive M1a local launcher (Windows). [KCH-90]
::
:: Mirrors the MVP1 launcher conventions (src\Loan Manager\run_windows.bat): a
:: readable version-check failure, a project-local .venv, quiet installs.
:: Steps whose infrastructure hasn't landed yet (migration runner: KCH-91,
:: service-account seed: KCH-92, FastAPI app: KCH-93) print a notice and skip
:: rather than failing the whole run -- see docs\LOCAL_SETUP_WINDOWS.md.

echo === FinHive -- Windows Local Setup ===

set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%"

:: --- Python version check (3.10 minimum, mirrors MVP1) ---
set PYTHON_CMD=
for %%p in (python3.14 python3.13 python3.12 python3.11 python3.10 python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! == 0 (
        for /f "tokens=2 delims= " %%v in ('%%p --version 2^>^&1') do (
            set VERSION=%%v
        )
        for /f "tokens=1,2 delims=." %%a in ("!VERSION!") do (
            set MAJOR=%%a
            set MINOR=%%b
        )
        if !MAJOR! GEQ 3 (
            if !MINOR! GEQ 10 (
                set PYTHON_CMD=%%p
                goto :found_python
            )
        )
    )
)

echo ERROR: Python 3.10 or higher is required but was not found.
echo Please install Python 3.10+ from https://www.python.org/downloads/
pause
exit /b 1

:found_python
echo Using: !PYTHON_CMD!

:: --- Node version check (20 minimum, matches .github\workflows\ci.yml) ---
where node >nul 2>&1
if not !errorlevel! == 0 (
    echo ERROR: Node.js 20 or higher is required but was not found.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=1 delims=." %%n in ('node -e "console.log(process.versions.node)"') do set NODE_MAJOR=%%n
if !NODE_MAJOR! LSS 20 (
    echo ERROR: Node.js 20 or higher is required ^(found via node --version^).
    node --version
    echo Please install Node.js 20+ from https://nodejs.org/
    pause
    exit /b 1
)
echo Using: Node
node --version

:: --- Python virtual environment ---
set VENV_DIR=%ROOT_DIR%.venv
if not exist "!VENV_DIR!" (
    echo Creating virtual environment...
    !PYTHON_CMD! -m venv "!VENV_DIR!"
)
call "!VENV_DIR!\Scripts\activate.bat"

echo Installing backend dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"

echo Installing frontend dependencies...
pushd "%ROOT_DIR%web"
call npm install --silent
popd

:: --- Database: local Supabase (Postgres + Auth), or a configured Supabase branch ---
if exist "%ROOT_DIR%ops\.env.local" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT_DIR%ops\.env.local") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
        )
    )
)

if defined DATABASE_URL (
    echo DATABASE_URL is set -- using the configured Supabase branch.
) else (
    where supabase >nul 2>&1
    if !errorlevel! == 0 (
        echo Starting local Supabase ^(Postgres + Auth^)...
        call supabase start
        set DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
    ) else (
        echo ERROR: no DATABASE_URL is set and the Supabase CLI was not found.
        echo Install it ^(https://supabase.com/docs/guides/cli^) to run Postgres locally,
        echo or set DATABASE_URL in ops\.env.local to point at a Supabase branch.
        pause
        exit /b 1
    )
)

:: --- Migrations (finhive\db\migrations.py, added by KCH-91) ---
!PYTHON_CMD! -c "import finhive.db.migrations" >nul 2>&1
if !errorlevel! == 0 (
    echo Applying migrations...
    python -m finhive.db.migrations
) else (
    echo NOTE: migration runner not yet available ^(KCH-91^) -- skipping.
)

:: --- Seed service account (finhive\db\seed_service_account.py, added by KCH-92) ---
!PYTHON_CMD! -c "import finhive.db.seed_service_account" >nul 2>&1
if !errorlevel! == 0 (
    echo Seeding service account...
    python -m finhive.db.seed_service_account
) else (
    echo NOTE: service account seed not yet available ^(KCH-92^) -- skipping.
)

:: --- Launch API and SPA together ---
!PYTHON_CMD! -c "import finhive.dev_server" >nul 2>&1
if !errorlevel! == 0 (
    echo Starting API on http://localhost:8000 ...
    start "FinHive API" cmd /c "uvicorn finhive.dev_server:app --reload --port 8000"
) else (
    echo NOTE: backend API is not yet scaffolded ^(KCH-93^) -- starting the SPA only.
)

echo Starting SPA on http://localhost:5173 ...
pushd "%ROOT_DIR%web"
call npm run dev
popd
