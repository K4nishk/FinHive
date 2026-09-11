@echo off
setlocal enabledelayedexpansion
:: run_local_windows.bat -- FinHive M1a local launcher (Windows). [KCH-90]
::
:: Mirrors the MVP1 launcher conventions (src\Loan Manager\run_windows.bat): a
:: readable version-check failure, a project-local .venv, quiet installs.
::
:: KCH-90's acceptance criteria is "a clean machine reaches a working local
:: app from a single command" -- migrations, the service-account seed, and
:: the API all have to actually run for that to be true. Their
:: infrastructure lands in separate tickets (migration runner: KCH-91,
:: service-account seed: KCH-94, FastAPI app: KCH-102). Until all three
:: exist, this script FAILS rather than silently launching an SPA-only app
:: and calling it done. Pass --allow-partial (or set ALLOW_PARTIAL_SETUP=1)
:: to opt into that partial run anyway for frontend-only work -- see
:: docs\LOCAL_SETUP_WINDOWS.md.

set ALLOW_PARTIAL=%ALLOW_PARTIAL_SETUP%
if "%ALLOW_PARTIAL%"=="" set ALLOW_PARTIAL=0
if "%~1"=="--allow-partial" set ALLOW_PARTIAL=1

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
    if not !errorlevel! == 0 (
        echo ERROR: failed to create the virtual environment at !VENV_DIR!.
        pause
        exit /b 1
    )
)
call "!VENV_DIR!\Scripts\activate.bat"

echo Installing backend dependencies...
python -m pip install --quiet --upgrade pip
if not !errorlevel! == 0 (
    echo ERROR: "pip install --upgrade pip" failed.
    pause
    exit /b 1
)
python -m pip install --quiet -e ".[dev]"
if not !errorlevel! == 0 (
    echo ERROR: "pip install -e .[dev]" failed.
    pause
    exit /b 1
)

echo Installing frontend dependencies...
pushd "%ROOT_DIR%web"
call npm install --silent
if not !errorlevel! == 0 (
    echo ERROR: "npm install" failed in web\.
    popd
    pause
    exit /b 1
)
popd

:: --- Database: local Supabase (Postgres + Auth), or a configured Supabase branch ---
if exist "%ROOT_DIR%ops\.env.local" (
    :: Delayed expansion treats "!" as variable-expansion syntax, which
    :: corrupts values like a password containing "!" (e.g. DATABASE_URL).
    :: Disable it for the parse, then re-enable it for the rest of the script.
    setlocal disabledelayedexpansion
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT_DIR%ops\.env.local") do (
        echo %%a| findstr /b /c:"#" >nul
        if errorlevel 1 set "%%a=%%b"
    )
    setlocal enabledelayedexpansion
)

if defined DATABASE_URL (
    echo DATABASE_URL is set -- using the configured Supabase branch.
) else (
    where supabase >nul 2>&1
    if !errorlevel! == 0 (
        docker info >nul 2>&1
        if not !errorlevel! == 0 (
            echo ERROR: the Supabase CLI needs a running Docker-compatible container runtime.
            echo Start Docker Desktop ^(or another Docker API-compatible runtime^) and retry,
            echo or set DATABASE_URL in ops\.env.local to point at a Supabase branch instead.
            pause
            exit /b 1
        )
        echo Starting local Supabase ^(Postgres + Auth^)...
        call supabase start
        if not !errorlevel! == 0 (
            echo ERROR: "supabase start" failed.
            pause
            exit /b 1
        )
        set DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
    ) else (
        echo ERROR: no DATABASE_URL is set and the Supabase CLI was not found.
        echo Install it ^(https://supabase.com/docs/guides/cli^) to run Postgres locally,
        echo or set DATABASE_URL in ops\.env.local to point at a Supabase branch.
        pause
        exit /b 1
    )
)

:: --- Track mandatory KCH-90 stages so a missing one blocks by default ---
set MISSING_STAGES=

:: --- Migrations (finhive\db\migrate.py, added by KCH-91) ---
!PYTHON_CMD! -c "import finhive.db.migrate" >nul 2>&1
if !errorlevel! == 0 (
    echo Applying migrations...
    python -m finhive.db.migrate
    if not !errorlevel! == 0 (
        echo ERROR: "python -m finhive.db.migrate" failed.
        pause
        exit /b 1
    )
) else (
    set "MISSING_STAGES=!MISSING_STAGES! - migration runner (KCH-91)"
)

:: --- Seed service account (finhive\db\seed_service_account.py, added by KCH-94) ---
!PYTHON_CMD! -c "import finhive.db.seed_service_account" >nul 2>&1
if !errorlevel! == 0 (
    echo Seeding service account...
    python -m finhive.db.seed_service_account
    if not !errorlevel! == 0 (
        echo ERROR: "python -m finhive.db.seed_service_account" failed.
        pause
        exit /b 1
    )
) else (
    set "MISSING_STAGES=!MISSING_STAGES! - service account seed (KCH-94)"
)

:: --- API (finhive\dev_server.py, added by KCH-102) ---
!PYTHON_CMD! -c "import finhive.dev_server" >nul 2>&1
if not !errorlevel! == 0 (
    set "MISSING_STAGES=!MISSING_STAGES! - backend API (KCH-102)"
)

if not "!MISSING_STAGES!"=="" (
    if not "!ALLOW_PARTIAL!"=="1" (
        echo ERROR: KCH-90 is not fully satisfiable yet -- missing:
        echo !MISSING_STAGES!
        echo This is a partial environment, not a working local app. Re-run once
        echo those land, or pass --allow-partial ^(or set ALLOW_PARTIAL_SETUP=1^) to
        echo launch the SPA-only subset anyway for frontend-only work.
        pause
        exit /b 1
    )
    echo WARNING: PARTIAL SETUP -- proceeding without:
    echo !MISSING_STAGES!
)

:: --- Launch API and SPA together ---
set API_SHOULD_START=0
!PYTHON_CMD! -c "import finhive.dev_server" >nul 2>&1
if !errorlevel! == 0 set API_SHOULD_START=1

if !API_SHOULD_START! == 1 (
    powershell -NoProfile -Command ^
        "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',8000)).Close();exit 0}catch{exit 1}" >nul 2>&1
    if !errorlevel! == 0 (
        echo ERROR: port 8000 is already in use.
        echo Stop whatever is listening and re-run.
        pause
        exit /b 1
    )

    echo Starting API on http://localhost:8000 ...
    start "FinHive API" cmd /c "uvicorn finhive.dev_server:app --reload --port 8000"

    echo Waiting for the API to become ready...
    set API_READY=0
    for /l %%i in (1,1,30) do (
        if !API_READY! == 0 (
            powershell -NoProfile -Command ^
                "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',8000)).Close();exit 0}catch{exit 1}" >nul 2>&1
            if !errorlevel! == 0 (
                set API_READY=1
            ) else (
                timeout /t 1 /nobreak >nul
            )
        )
    )
    if not !API_READY! == 1 (
        echo ERROR: API not ready on :8000 within 30s.
        pause
        exit /b 1
    )
    echo API is ready.
) else (
    echo Starting the SPA only -- no backend API.
)

echo Starting SPA on http://localhost:5173 ...
pushd "%ROOT_DIR%web"
call npm run dev
popd
