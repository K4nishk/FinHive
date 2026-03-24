@echo off
REM Loan Manager launcher for Windows.
REM Creates a virtual environment, installs dependencies, and starts the app.

REM Check Python version (requires Python 3.10+)
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: Python was not found. Please install Python 3.10 or later from https://www.python.org/downloads/
    pause
    exit /b 1
)
FOR /F "tokens=2 delims= " %%V IN ('python --version 2^>^&1') DO SET PY_VERSION=%%V
FOR /F "tokens=1,2 delims=." %%A IN ("%PY_VERSION%") DO (
    SET PY_MAJOR=%%A
    SET PY_MINOR=%%B
)
IF %PY_MAJOR% LSS 3 (
    echo ERROR: Python 3.10 or later is required. Found Python %PY_VERSION%. Please upgrade from https://www.python.org/downloads/
    pause
    exit /b 1
)
IF %PY_MAJOR% EQU 3 IF %PY_MINOR% LSS 10 (
    echo ERROR: Python 3.10 or later is required. Found Python %PY_VERSION%. Please upgrade from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python %PY_VERSION% detected. OK.

SET SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

SET VENV_DIR=%SCRIPT_DIR%.venv

IF NOT EXIST "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

echo Activating virtual environment...
CALL "%VENV_DIR%\Scripts\activate.bat"

echo Installing dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo Starting Loan Manager...
python main.py

pause
