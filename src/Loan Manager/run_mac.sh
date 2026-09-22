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
# Resolved from this script's own location so every path below is independent of
# where the user invoked it from. `cd -P` follows symlinks to a real directory.
APP_DIR="$(cd -P "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd -P "$APP_DIR/../.." && pwd)"

VENV_DIR="$APP_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/upgrade requirements
echo "Installing requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r "$APP_DIR/requirements.txt"

# The finhive package supplies encryption at rest (ARB D-15). Installed from a
# path derived from THIS SCRIPT's location, never a relative path in
# requirements.txt — pip resolves those against its own working directory, so
# `-e ../..` installs whatever happens to sit two levels above the caller.
pip install --quiet -e "$REPO_ROOT"

# Encryption master key. Sourced here because the app reads os.environ and has no
# dotenv dependency; without this, ops/.env.local is a file nothing loads.
if [ -f "$REPO_ROOT/ops/.env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_ROOT/ops/.env.local"
    set +a
fi

# Run the application
echo "Starting Loan Manager..."
cd "$APP_DIR"
python -m loan_manager.main
