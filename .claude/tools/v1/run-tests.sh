#!/bin/bash
# LoanTracker Test Runner Script
# Run all automated tests for the application

set -e  # Exit on error

echo "🧪 LoanTracker Test Suite Runner"
echo "================================="
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "❌ Virtual environment not found at $SCRIPT_DIR/venv"
    echo "   Please create it first with: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

# Navigate to backend directory
cd "$SCRIPT_DIR/backend"

# Check if pytest is installed
if ! python -m pytest --version &> /dev/null; then
    echo "❌ pytest not found. Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "📦 Running Unit Tests..."
echo "------------------------"
python -m pytest tests/unit/ -v

echo ""
echo "🌐 Running Integration Tests..."
echo "--------------------------------"
python -m pytest tests/integration/ -v

echo ""
echo "📊 Generating Coverage Report..."
echo "---------------------------------"
python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

echo ""
echo "✅ All Tests Complete!"
echo ""
echo "📈 Coverage report generated: backend/htmlcov/index.html"
echo "   Open with: open backend/htmlcov/index.html"
echo ""

# Deactivate virtual environment
deactivate
