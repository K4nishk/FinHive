@echo off
REM LoanTracker - Windows Startup Script
REM Version: 1.0.0

echo ========================================
echo  LoanTracker - Loan Management System
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.11 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Navigate to backend directory
cd /d "%~dp0backend"

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install minimal requirements
echo Installing core dependencies...
echo This may take 2-3 minutes on first run...
pip install -q -r requirements-minimal.txt
if errorlevel 1 (
    echo ERROR: Failed to install core dependencies
    pause
    exit /b 1
)
echo Core packages installed successfully!
echo.

REM Try to install cryptography (optional)
echo Installing cryptography (optional)...
pip install -q --no-cache-dir cryptography >nul 2>&1
if errorlevel 1 (
    echo Cryptography installation skipped
    echo Encryption will be disabled
) else (
    echo Cryptography installed - encryption available
)
echo.

REM Try to install pandas (optional)
echo Installing pandas (optional)...
pip install -q --no-cache-dir pandas >nul 2>&1
if errorlevel 1 (
    echo Pandas installation skipped
    echo Will use built-in CSV module
) else (
    echo Pandas installed successfully
)
echo.

REM Create necessary directories
if not exist "logs\" mkdir logs
if not exist "engine_output\" mkdir engine_output

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating default configuration...
    (
        echo # LoanTracker Configuration
        echo STORAGE_TYPE=csv
        echo ENCRYPTION_KEY=
        echo CSV_OUTPUT_DIR=./engine_output
        echo CSV_FILENAME=loan_records.csv
        echo BACKEND_HOST=0.0.0.0
        echo BACKEND_PORT=8000
        echo BACKEND_RELOAD=False
        echo LOG_LEVEL=INFO
    ) > .env
)

echo.
echo ========================================
echo  Starting LoanTracker Server...
echo ========================================
echo.
echo Access the application at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the FastAPI server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

REM If server stops, pause to show any errors
pause
