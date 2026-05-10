#!/bin/bash
# First-time setup script for UPSC 10-Day Prep System
# Run: bash setup.sh

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Setting up UPSC 10-Day Prep System in: $PROJECT_DIR"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Install from python.org"
    exit 1
fi

# 2. Install Python deps
echo "\n Installing Python dependencies..."
pip3 install -r "$PROJECT_DIR/scripts/requirements.txt"

# 3. Check tesseract
if ! command -v tesseract &> /dev/null; then
    echo "\n Installing Tesseract (requires Homebrew)..."
    brew install tesseract poppler
fi

# 4. Initialise database
echo "\n Initialising database..."
cd "$PROJECT_DIR" && python3 scripts/db_init.py

# 5. Check Node.js
if ! command -v node &> /dev/null; then
    echo "\nWARNING: Node.js not found."
    echo "Install from: https://nodejs.org (LTS version)"
    echo "After installing Node.js, run: cd web && npm install"
else
    echo "\n Installing web dependencies..."
    cd "$PROJECT_DIR/web" && npm install
fi

echo "\n Setup complete!"
echo "\nNext steps:"
echo "  1. Update .env with your new Anthropic API key"
echo "  2. Run ingestion:   python3 scripts/ingest.py"
echo "  3. Run PYQ ingest:  python3 scripts/ingest_pyq.py  (runs overnight)"
echo "  4. Start backend:   cd backend && uvicorn server:app --host 0.0.0.0 --port 8000"
echo "  5. Start web:       cd web && npm run dev"
echo "  6. Open browser:    http://localhost:3000"
