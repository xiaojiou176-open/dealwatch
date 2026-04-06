#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=========================================="
echo "DealWatch Bootstrap"
echo "=========================================="
echo ""

if ! command -v python3 &> /dev/null; then
  echo "ERROR: python3 not found. Please install Python 3.11+."
  exit 1
fi

if ! command -v uv &> /dev/null; then
  echo "ERROR: uv not found. Install uv first, then rerun bootstrap."
  exit 1
fi
uv sync --frozen --group dev
uv run python -m playwright install chromium

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "OK: created .env from .env.example"
fi

echo ""
echo "Done."
echo "Next:"
echo "  Product check : PYTHONPATH=src uv run python -m dealwatch maintenance --dry-run"
echo "  Product API   : PYTHONPATH=src uv run python -m dealwatch server"
echo "  Product Worker: PYTHONPATH=src uv run python -m dealwatch worker"
echo "  Compare flow  : open http://127.0.0.1:5173/#compare after frontend starts"
