@echo off
REM LoanTracker Quick Start Script for Windows
REM Usage: start.bat

echo ====================================
echo 🏦 LoanTracker - Starting Application
echo ====================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker is not installed!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo ✅ Docker is running
echo.

REM Check if .env file exists
if not exist .env (
    echo 📝 Creating .env file from template...
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo. > .env
    )
    echo ✅ Created .env file - you can customize it later
    echo.
)

REM Create necessary directories
echo 📁 Creating directories...
if not exist engine_output mkdir engine_output
if not exist logs mkdir logs
echo ✅ Directories created
echo.

REM Start the application
echo 🚀 Starting LoanTracker with Docker Compose...
docker-compose up -d

REM Wait for service to be ready
echo ⏳ Waiting for service to start...
timeout /t 5 /nobreak >nul

REM Check if service is running
docker-compose ps | findstr "Up" >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ LoanTracker is running!
    echo.
    echo 🌐 Open your browser and go to:
    echo    http://localhost:8000
    echo.
    echo 📊 Your data will be stored in:
    echo    engine_output\loan_records.csv
    echo.
    echo 🛑 To stop the application, run:
    echo    docker-compose down
    echo.
    echo 📖 For more information, see README.md or USER_GUIDE_WINDOWS.md
    echo.
) else (
    echo ❌ Failed to start LoanTracker
    echo Check logs with: docker-compose logs
    pause
    exit /b 1
)

pause
