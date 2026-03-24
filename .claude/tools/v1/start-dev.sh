#!/bin/bash
# LoanTracker Development Start (No Docker Required)
# Usage: ./start-dev.sh

set -e

echo "🏦 LoanTracker - Starting in Development Mode"
echo "=============================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Install from: https://www.python.org/downloads/"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip first
echo "⬆️  Upgrading pip..."
pip install -q --upgrade pip setuptools wheel 2>/dev/null || pip install --upgrade pip

# Install backend dependencies
echo "📥 Installing backend dependencies..."
echo "   This may take 2-3 minutes on first run..."
cd backend

# Try minimal installation first (faster, no compilation needed)
echo "   Installing core packages..."
if pip install -q -r requirements-minimal.txt; then
    echo "✅ Core packages installed"

    # Try adding cryptography separately (optional - for encryption)
    echo "   Installing cryptography (optional, for encryption)..."
    if pip install -q --no-cache-dir cryptography 2>/dev/null; then
        echo "✅ Cryptography installed - encryption available"
        export USE_ENCRYPTION=true
    else
        echo "⚠️  Cryptography installation skipped"
        echo "   Encryption will be disabled (set ENCRYPTION_KEY= in .env)"
        export USE_ENCRYPTION=false
    fi

    # Try adding pandas separately (optional - for performance)
    echo "   Installing pandas (optional, for better performance)..."
    if pip install -q --no-cache-dir pandas 2>/dev/null; then
        echo "✅ Pandas installed successfully"
        export USE_PANDAS=true
    else
        echo "⚠️  Pandas installation skipped (will use built-in CSV module)"
        echo "   App will work fine without pandas!"
        export USE_PANDAS=false
    fi
else
    echo "❌ Failed to install minimal requirements"
    echo "   Please check your internet connection and try again"
    exit 1
fi

cd ..

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p engine_output logs

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOL
# LoanTracker Configuration
STORAGE_TYPE=csv
ENCRYPTION_KEY=
CSV_OUTPUT_DIR=./engine_output
CSV_FILENAME=loan_records.csv
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
LOG_LEVEL=INFO
EOL
fi

# Warn about encryption if key is set but cryptography not available
if [ "$USE_ENCRYPTION" = "false" ] && grep -q "^ENCRYPTION_KEY=..*" .env 2>/dev/null; then
    echo ""
    echo "⚠️  WARNING: ENCRYPTION_KEY is set but cryptography is not installed!"
    echo "   The app will fail to start. Please either:"
    echo "   1. Install cryptography: pip install cryptography"
    echo "   2. Disable encryption: Set ENCRYPTION_KEY= (empty) in .env"
    echo ""
fi

echo ""
echo "✅ Backend setup complete!"
echo ""
echo "🚀 Starting FastAPI backend server..."
echo "   Access at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the backend
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
