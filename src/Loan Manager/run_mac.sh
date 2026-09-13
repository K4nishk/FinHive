#!/bin/bash
set -e

echo "=== Loan Manager — macOS Launcher ==="

# Python version check
PYTHON_CMD=""
# Python 3.13+ recommended; 3.10 minimum
for cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.10 or higher is required but was not found."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

echo "Using: $($PYTHON_CMD --version)"

# Setup virtual environment
VENV_DIR="$(dirname "$0")/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/upgrade requirements
echo "Installing requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r "$(dirname "$0")/requirements.txt"

# Run the application
echo "Starting Loan Manager..."
cd "$(dirname "$0")"
python -m loan_manager.main
