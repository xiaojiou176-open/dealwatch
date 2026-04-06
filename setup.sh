#!/bin/bash

#########################################################
# DealWatch Setup Script
# Automated setup helper for local environment bootstrap
#########################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "DealWatch Setup Script"
echo "=========================================="
echo ""

#########################################################
# Step 1: Check Python version
#########################################################
echo "[1/6] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 was not found. Install Python 3.11+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python version is too old (current: $PYTHON_VERSION, required: $REQUIRED_VERSION+)."
    exit 1
fi

echo "OK: Python version $(python3 --version)"
echo ""

#########################################################
# Step 2: Check uv
#########################################################
echo "[2/6] Checking uv..."
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv was not found. Install uv first, then rerun setup."
    exit 1
fi

echo "OK: uv $(uv --version)"
echo ""

#########################################################
# Step 3: Sync dependencies
#########################################################
echo "[3/6] Syncing dependencies with uv..."
uv sync --frozen --group dev

echo "OK: dependencies installed"
echo ""

#########################################################
# Step 4: Install the Playwright browser runtime
#########################################################
echo "[4/6] Installing Playwright browser runtime..."
uv run python -m playwright install chromium
echo "OK: Playwright browser runtime installed"
echo ""

#########################################################
# Step 5: Prepare configuration
#########################################################
echo "[5/6] Preparing configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "OK: created .env from .env.example"
        echo "ACTION: edit .env and replace the placeholder values before you run the product."
    else
        echo "WARNING: .env.example was not found, so create .env manually."
    fi
else
    echo "OK: .env already exists"
fi
echo ""

#########################################################
# Step 6: Verify the install
#########################################################
echo "[6/6] Verifying the install..."
uv run python -c "import aiosqlite; print('✓ aiosqlite: OK')" || echo "❌ aiosqlite: FAILED"
uv run python -c "import playwright; print('✓ playwright: OK')" || echo "❌ playwright: FAILED"
uv run python -c "import pydantic; print('✓ pydantic: OK')" || echo "❌ pydantic: FAILED"
echo ""

#########################################################
# Finish
#########################################################
echo "=========================================="
echo "Setup complete."
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env and replace the placeholder values:"
echo "   - ZIP_CODE: your ZIP code"
echo "   - USE_LLM: true/false"
echo "   - LLM_API_KEY: only if USE_LLM=true"
echo "   - SMTP_*: only if you want SMTP email delivery"
echo ""
echo "2. Run the first verification pass:"
echo "   PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run"
echo "   PYTHONPATH=src uv run python -m dealwatch server"
echo "   PYTHONPATH=src uv run python -m dealwatch worker"
echo "   # Or use the legacy bridge:"
echo "   PYTHONPATH=src uv run python -m dealwatch legacy --store weee --zip <your-zip-code>"
echo ""
echo "3. Read the repository docs for more details:"
echo "   open README.md for setup notes and verification commands"
echo ""
