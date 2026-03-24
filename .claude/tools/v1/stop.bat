@echo off
REM LoanTracker Stop Script for Windows
REM Usage: stop.bat

echo 🛑 Stopping LoanTracker...
echo.

docker-compose down

echo.
echo ✅ LoanTracker stopped
echo.
echo Your data is preserved in: engine_output\loan_records.csv
echo To start again, run: start.bat
echo.

pause
