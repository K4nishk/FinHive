#!/bin/bash
# LoanTracker Stop Script for Mac/Linux
# Usage: ./stop.sh

echo "🛑 Stopping LoanTracker..."

docker-compose down

echo "✅ LoanTracker stopped"
echo ""
echo "Your data is preserved in: engine_output/loan_records.csv"
echo "To start again, run: ./start.sh"
