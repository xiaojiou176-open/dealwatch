#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required for the quickstart stack." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' is required for the quickstart stack. Install Docker Compose v2 support and try again." >&2
  exit 1
fi

created_env=0
if [ ! -f ".env" ]; then
  cp .env.example .env
  created_env=1
  echo "OK: created .env from .env.example"
fi

if [ "${1:-}" = "--check" ]; then
  docker compose config -q
  if [ "$created_env" -eq 1 ]; then
    rm .env
    echo "OK: removed temporary .env created for --check"
  fi
  echo "OK: quickstart stack config is valid"
  exit 0
fi

echo "Starting DealWatch local stack..."
echo "Open http://127.0.0.1:5173/#compare after the services are ready."
exec docker compose up --build "$@"
