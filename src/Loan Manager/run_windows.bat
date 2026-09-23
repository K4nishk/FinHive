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

REM Encryption master key (ARB D-15). ops\.env.local is written in POSIX `export`
REM syntax for the mac launcher; parsing it reliably in batch is more trouble than
REM it earns, so Windows sets the variables directly. The app fails at startup with
REM instructions if they are absent -- see docs\LOCAL_SETUP_WINDOWS.md.
if not defined FINHIVE_KEY_VERSION (
    echo.
    echo WARNING: FINHIVE_KEY_VERSION is not set. Encryption at rest is mandatory,
    echo          so Loan Manager will refuse to start. Set it and the matching
    echo          FINHIVE_MASTER_KEY_V^<n^> first - see docs\LOCAL_SETUP_WINDOWS.md.
    echo.
)

:: Run application
echo Starting Loan Manager...
cd /d "%~dp0"
python -m loan_manager.main
pause
