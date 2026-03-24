#!/bin/bash
# Package LoanTracker for Windows distribution

set -e

echo "========================================="
echo " LoanTracker - Windows Package Builder"
echo "========================================="
echo ""

# Configuration
VERSION="1.0.0"
PACKAGE_NAME="LoanTracker-Windows-v${VERSION}"
DIST_DIR="dist"
PACKAGE_DIR="${DIST_DIR}/${PACKAGE_NAME}"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "${DIST_DIR}"
mkdir -p "${PACKAGE_DIR}"

# Copy necessary files
echo "Copying application files..."

# Backend files
mkdir -p "${PACKAGE_DIR}/backend"
cp -r backend/app "${PACKAGE_DIR}/backend/"
cp -r backend/static "${PACKAGE_DIR}/backend/"
cp backend/requirements.txt "${PACKAGE_DIR}/backend/"
cp backend/requirements-minimal.txt "${PACKAGE_DIR}/backend/"

# Root files
cp start-windows.bat "${PACKAGE_DIR}/"
cp sample_loans.csv "${PACKAGE_DIR}/"
cp README.md "${PACKAGE_DIR}/"
cp WINDOWS_SETUP.md "${PACKAGE_DIR}/"
cp TROUBLESHOOTING.md "${PACKAGE_DIR}/"

# Create placeholder directories
mkdir -p "${PACKAGE_DIR}/backend/logs"
mkdir -p "${PACKAGE_DIR}/backend/engine_output"

# Create .env.example
cat > "${PACKAGE_DIR}/backend/.env.example" <<EOF
# LoanTracker Configuration
# Copy this file to .env and customize as needed

# Storage
STORAGE_TYPE=csv
CSV_OUTPUT_DIR=./engine_output
CSV_FILENAME=loan_records.csv

# Encryption (optional - leave empty to disable)
ENCRYPTION_KEY=

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_RELOAD=False

# Logging
LOG_LEVEL=INFO
EOF

# Create README in package
cat > "${PACKAGE_DIR}/START_HERE.txt" <<EOF
========================================
 LoanTracker - Windows Package
 Version ${VERSION}
========================================

QUICK START (30 seconds):
------------------------
1. Double-click: start-windows.bat
2. Wait for setup to complete (first run: 2-3 minutes)
3. Open browser: http://localhost:8000

PREREQUISITES:
--------------
- Windows 10/11 (64-bit)
- Python 3.11 or higher
  Download from: https://www.python.org/downloads/
  IMPORTANT: Check "Add Python to PATH" during installation

DOCUMENTATION:
--------------
- WINDOWS_SETUP.md     - Complete Windows setup guide
- README.md            - Full project documentation
- TROUBLESHOOTING.md   - Common issues and solutions

SAMPLE DATA:
------------
- sample_loans.csv     - 10 test loans for trying the app
  (Import via: Import CSV tab in the app)

SUPPORT:
--------
- Check TROUBLESHOOTING.md for common issues
- Logs available in: backend/logs/loantracker.log

========================================
Built with ❤️ for Windows users
========================================
EOF

# Create a LICENSE file
cat > "${PACKAGE_DIR}/LICENSE.txt" <<EOF
MIT License

Copyright (c) 2026 LoanTracker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# Create version info file
cat > "${PACKAGE_DIR}/VERSION.txt" <<EOF
LoanTracker for Windows
Version: ${VERSION}
Build Date: $(date +"%Y-%m-%d")
Platform: Windows 10/11 (64-bit)
Python Required: 3.11+

Features:
- Loan management (CRUD operations)
- Currency support (INR, CAD)
- Commission calculator
- CSV import/export
- Reports and statistics
- Minimal clean theme
- Optional encryption

Package Contents:
- Backend application
- Static frontend (HTML/CSS/JS)
- Sample data (10 test loans)
- Documentation (Windows setup, troubleshooting)
- Startup scripts (start-windows.bat)

Installation:
1. Extract ZIP file
2. Double-click start-windows.bat
3. Open http://localhost:8000

For detailed instructions, see WINDOWS_SETUP.md
EOF

# Create ZIP archive
echo "Creating ZIP package..."
cd "${DIST_DIR}"
zip -r -q "${PACKAGE_NAME}.zip" "${PACKAGE_NAME}"
cd ..

# Calculate package size
PACKAGE_SIZE=$(du -h "${DIST_DIR}/${PACKAGE_NAME}.zip" | cut -f1)

echo ""
echo "========================================="
echo " Package created successfully!"
echo "========================================="
echo ""
echo "Package: ${DIST_DIR}/${PACKAGE_NAME}.zip"
echo "Size: ${PACKAGE_SIZE}"
echo ""
echo "Contents:"
echo "  - Application files (backend + frontend)"
echo "  - Sample data (10 loans)"
echo "  - Documentation (3 files)"
echo "  - Windows startup script"
echo ""
echo "To test:"
echo "  1. Extract ${PACKAGE_NAME}.zip"
echo "  2. Run start-windows.bat"
echo "  3. Open http://localhost:8000"
echo ""
echo "Ready for distribution! ✅"
echo ""
