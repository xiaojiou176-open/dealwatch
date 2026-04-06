#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN=""
API_PID=""
WORKER_PID=""
SMOKE_LOG_DIR="${SMOKE_LOG_DIR:-.runtime-cache/operator/smoke}"

if [[ "${SMOKE_LOG_DIR}" != /* ]]; then
  SMOKE_LOG_DIR="${ROOT}/${SMOKE_LOG_DIR}"
fi

API_SMOKE_LOG="${SMOKE_LOG_DIR}/api-smoke.log"
WORKER_SMOKE_LOG="${SMOKE_LOG_DIR}/worker-smoke.log"

cleanup() {
  if [[ -n "${WORKER_PID}" ]] && kill -0 "${WORKER_PID}" >/dev/null 2>&1; then
    kill "${WORKER_PID}" >/dev/null 2>&1 || true
    wait "${WORKER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" >/dev/null 2>&1; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "ERROR: no usable Python interpreter found."
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  export POSTGRES_PORT="${POSTGRES_PORT:-55432}"
  export POSTGRES_USER="${POSTGRES_USER:-dealwatch}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dealwatch}"
  export POSTGRES_DB="${POSTGRES_DB:-dealwatch}"
  export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
fi

export OWNER_EMAIL="${OWNER_EMAIL:-owner@example.com}"
export OWNER_DISPLAY_NAME="${OWNER_DISPLAY_NAME:-DealWatch Owner}"
export OWNER_BOOTSTRAP_TOKEN="${OWNER_BOOTSTRAP_TOKEN:-smoke-token}"
export POSTMARK_FROM_EMAIL="${POSTMARK_FROM_EMAIL:-dealwatch@example.com}"
export POSTMARK_MESSAGE_STREAM="${POSTMARK_MESSAGE_STREAM:-outbound}"
export ZIP_CODE="${ZIP_CODE:-98004}"
export WEBUI_DEV_URL="${WEBUI_DEV_URL:-http://127.0.0.1:5173}"
export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8000}"
export WORKER_POLL_SECONDS="${WORKER_POLL_SECONDS:-60}"

mkdir -p "${SMOKE_LOG_DIR}"
rm -f "${API_SMOKE_LOG}" "${WORKER_SMOKE_LOG}"

echo "==> Bootstrapping owner CLI"
PYTHONPATH=src "$PYTHON_BIN" -m dealwatch bootstrap-owner \
  --email "$OWNER_EMAIL" \
  --display-name "$OWNER_DISPLAY_NAME" \
  --token "$OWNER_BOOTSTRAP_TOKEN"

echo "==> Running product data smoke"
PYTHONPATH=src "$PYTHON_BIN" scripts/product_smoke.py

echo "==> Booting API"
PYTHONPATH=src "$PYTHON_BIN" -m dealwatch server > "${API_SMOKE_LOG}" 2>&1 &
API_PID="$!"

"$PYTHON_BIN" - <<'PY'
import os
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

api_host = os.environ.get("API_HOST", "127.0.0.1")
api_port = os.environ.get("API_PORT", "8000")
target = f"http://{api_host}:{api_port}/api/health"

for _ in range(30):
    try:
        with urlopen(target, timeout=2) as response:
            body = response.read().decode("utf-8")
            if response.status == 200 and '"status"' in body:
                print(f"API_OK {target}")
                sys.exit(0)
    except URLError:
        time.sleep(1)

print(f"API_HEALTH_FAILED {target}", file=sys.stderr)
sys.exit(1)
PY

echo "==> Booting worker"
PYTHONPATH=src "$PYTHON_BIN" -m dealwatch worker > "${WORKER_SMOKE_LOG}" 2>&1 &
WORKER_PID="$!"
sleep 5

if ! kill -0 "${WORKER_PID}" >/dev/null 2>&1; then
  echo "ERROR: worker exited during smoke boot." >&2
  exit 1
fi

echo "WORKER_OK pid=${WORKER_PID}"
