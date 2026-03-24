#!/usr/bin/env bash
# Loan Manager launcher for macOS.
# Creates a virtual environment, installs dependencies, and starts the app.
set -euo pipefail

# Check Python version (requires Python 3.10+)
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 was not found. Please install Python 3.10 or later from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10 or later is required. Found Python ${PY_VERSION}. Please upgrade from https://www.python.org/downloads/"
    exit 1
fi

echo "Python ${PY_VERSION} detected. OK."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Starting Loan Manager..."
python main.py
