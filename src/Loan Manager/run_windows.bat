@echo off
setlocal enabledelayedexpansion

echo === Loan Manager -- Windows Launcher ===

:: Python version check
set PYTHON_CMD=
:: Python 3.13+ recommended; 3.10 minimum
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

:: Setup virtual environment
set VENV_DIR=%~dp0.venv
if not exist "!VENV_DIR!" (
    echo Creating virtual environment...
    !PYTHON_CMD! -m venv "!VENV_DIR!"
)

:: Activate venv
call "!VENV_DIR!\Scripts\activate.bat"

:: Install requirements
echo Installing requirements...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "%~dp0requirements.txt"

REM finhive supplies encryption at rest (ARB D-15). Installed from a path derived
REM from THIS SCRIPT's location (%~dp0), never a relative path inside
REM requirements.txt -- pip resolves those against its own working directory.
python -m pip install --quiet -e "%~dp0..\.."

REM Encryption master key (ARB D-15). Nothing to set: with no FINHIVE_KEY_VERSION
REM in the environment, the app creates data\encryption\master_key.key on first
REM launch and reuses it after that (F-006). A key that only lived in one
REM PowerShell window was lost with the window. See docs\AskFinHive_instructions.md.
if not defined FINHIVE_KEY_VERSION (
    echo Encryption key file: %~dp0data\encryption\master_key.key
    echo   Created on first launch if missing. Back it up - without it your data cannot be read.
)

:: Run application
cd /d "%~dp0"

REM Demo ledger (MVP1.1): "run_windows.bat demo" seeds a synthetic 27-loan
REM ledger outside data\ on first use and launches on it; "demo-reset" reseeds
REM it. Uses this launcher's venv python, so nothing needs activating by hand
REM and no FINHIVE_DB_PATH has to be set in the right window (F-003). Override
REM the location with FINHIVE_DEMO_DB. Without an argument the app opens your
REM real ledger.
set "MODE=%~1"
set DEMO=0
if /i "!MODE!"=="demo" set DEMO=1
if /i "!MODE!"=="demo-reset" set DEMO=1
if "!DEMO!"=="1" (
    if not defined FINHIVE_DEMO_DB set "FINHIVE_DEMO_DB=%USERPROFILE%\finhive-demo\demo.db"
    for %%d in ("!FINHIVE_DEMO_DB!") do if not exist "%%~dpd" mkdir "%%~dpd"
    REM Seed with FINHIVE_DB_PATH unset: the seeder refuses to overwrite the
    REM database the app is currently pointed at.
    set "FINHIVE_DB_PATH="
    set SEED_RC=0
    if /i "!MODE!"=="demo-reset" (
        python -m loan_manager.infrastructure.seed --db "!FINHIVE_DEMO_DB!" --replace
        set SEED_RC=!errorlevel!
    ) else if not exist "!FINHIVE_DEMO_DB!" (
        python -m loan_manager.infrastructure.seed --db "!FINHIVE_DEMO_DB!"
        set SEED_RC=!errorlevel!
    )
    set "FINHIVE_DB_PATH=!FINHIVE_DEMO_DB!"
    if not "!SEED_RC!"=="0" (
        echo ERROR: could not create the demo ledger -- see the message above.
        pause
        exit /b 1
    )
    echo Using the demo ledger: !FINHIVE_DB_PATH!
)

echo Starting Loan Manager...
python -m loan_manager.main
pause
