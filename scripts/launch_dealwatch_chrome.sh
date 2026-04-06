#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEALWATCH_ENV_FILE:-${ROOT_DIR}/.env}"
PS_BIN="${DEALWATCH_PS_BIN:-ps}"
OPEN_BIN="${DEALWATCH_OPEN_BIN:-open}"
PYTHON_BIN="${DEALWATCH_PYTHON_BIN:-python3}"
READY_RETRIES="${DEALWATCH_READY_RETRIES:-20}"
MAX_BROWSER_INSTANCES="${DEALWATCH_MAX_BROWSER_INSTANCES:-6}"
ENSURE_TABS_SCRIPT="${ROOT_DIR}/scripts/open_dealwatch_account_pages.py"

read_env_json() {
  "${PYTHON_BIN}" - "${ENV_FILE}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
payload = {}
if env_file.exists():
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        payload[key.strip()] = value.strip().strip('"').strip("'")
keys = [
    "CHROME_USER_DATA_DIR",
    "CHROME_PROFILE_NAME",
    "CHROME_PROFILE_DIRECTORY",
    "CHROME_CDP_URL",
    "CHROME_REMOTE_DEBUG_PORT",
]
print(json.dumps({key: payload.get(key, "") for key in keys}))
PY
}

ENV_JSON="$(read_env_json)"

export CHROME_USER_DATA_DIR="$("${PYTHON_BIN}" - <<'PY' "${ENV_JSON}"
import json, pathlib, sys
payload = json.loads(sys.argv[1])
value = payload.get("CHROME_USER_DATA_DIR", "")
print(pathlib.Path(value).expanduser() if value else "")
PY
)"
export CHROME_PROFILE_NAME="$("${PYTHON_BIN}" - <<'PY' "${ENV_JSON}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get("CHROME_PROFILE_NAME", ""))
PY
)"
export CHROME_PROFILE_DIRECTORY="$("${PYTHON_BIN}" - <<'PY' "${ENV_JSON}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get("CHROME_PROFILE_DIRECTORY", ""))
PY
)"
export CHROME_REMOTE_DEBUG_PORT="$("${PYTHON_BIN}" - <<'PY' "${ENV_JSON}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload.get("CHROME_REMOTE_DEBUG_PORT", "9333") or "9333")
PY
)"

if [[ -z "${CHROME_USER_DATA_DIR}" || -z "${CHROME_PROFILE_NAME}" || -z "${CHROME_PROFILE_DIRECTORY}" ]]; then
  echo "DealWatch Chrome launcher refused: CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME, and CHROME_PROFILE_DIRECTORY must all be configured in .env." >&2
  exit 1
fi

IDENTITY_JSON="$("${PYTHON_BIN}" "${ENSURE_TABS_SCRIPT}" --env-file "${ENV_FILE}" --write-only --json)"
IDENTITY_PAGE_URL="$("${PYTHON_BIN}" - <<'PY' "${IDENTITY_JSON}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["identity_page_url"])
PY
)"

print_lane_summary() {
  "${PYTHON_BIN}" - <<'PY' "${1}"
import json, sys

payload = json.loads(sys.argv[1])
print(f"identity_page_path={payload['identity_page_path']}")
print(f"identity_page_url={payload['identity_page_url']}")
print(f"identity_label={payload['identity_label']}")
print(f"identity_accent={payload['identity_accent']}")
targets = payload.get("targets", [])
if targets:
    print("ensured_targets=" + ",".join(item["slug"] for item in targets))
for item in targets:
    print(
        "target="
        f"{item['label']} | action={item['action']} | requested_url={item['requested_url']} | matched_url={item['matched_url'] or ''}"
    )
PY
}

PS_COUNTS="$("${PYTHON_BIN}" - <<'PY' "${CHROME_USER_DATA_DIR}" "${CHROME_PROFILE_DIRECTORY}" "${PS_BIN}"
from __future__ import annotations

import subprocess
import sys

target_root = sys.argv[1]
target_profile = sys.argv[2]
ps_bin = sys.argv[3]
result = subprocess.run(
    [ps_bin, "-axo", "comm=,args="],
    check=True,
    capture_output=True,
    text=True,
)
chrome_exec = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
browser_exec_markers = (
    chrome_exec,
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Safari.app/Contents/MacOS/Safari",
)
matching_count = 0
total_browser_instances = 0
for raw_line in result.stdout.splitlines():
    line = raw_line.strip()
    if not line:
        continue
    if any(marker in line for marker in browser_exec_markers):
        total_browser_instances += 1
    if chrome_exec in line and f"--user-data-dir={target_root}" in line and f"--profile-directory={target_profile}" in line:
        matching_count += 1
print(f"{matching_count} {total_browser_instances}")
PY
)"
read -r EXISTING_COUNT TOTAL_BROWSER_INSTANCES <<<"${PS_COUNTS}"
TOTAL_BROWSER_INSTANCES="${TOTAL_BROWSER_INSTANCES:-0}"

if [[ "${EXISTING_COUNT}" != "0" ]]; then
  if "${PYTHON_BIN}" - <<'PY' "${CHROME_REMOTE_DEBUG_PORT}" >/dev/null 2>&1
import json
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as response:
    json.load(response)
PY
  then
    ENSURE_JSON="$("${PYTHON_BIN}" "${ENSURE_TABS_SCRIPT}" --env-file "${ENV_FILE}" --json)"
    echo "DealWatch Chrome launcher: reusing existing dedicated Chrome instance for ${CHROME_PROFILE_NAME} (${CHROME_PROFILE_DIRECTORY})."
    print_lane_summary "${ENSURE_JSON}"
    exit 0
  fi
  echo "DealWatch Chrome launcher refused: matching Chrome process exists for ${CHROME_PROFILE_NAME} (${CHROME_PROFILE_DIRECTORY}), but CDP listener ${CHROME_REMOTE_DEBUG_PORT} is not reachable." >&2
  exit 1
fi

if (( TOTAL_BROWSER_INSTANCES > MAX_BROWSER_INSTANCES )); then
  echo "DealWatch Chrome launcher refused: machine already has ${TOTAL_BROWSER_INSTANCES} browser instances, above DealWatch limit ${MAX_BROWSER_INSTANCES}. Finish non-browser work first or wait for active owners to recover their lanes before launching another dedicated Chrome instance." >&2
  exit 1
fi

"${OPEN_BIN}" -na "Google Chrome" --args \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port="${CHROME_REMOTE_DEBUG_PORT}" \
  --user-data-dir="${CHROME_USER_DATA_DIR}" \
  --profile-directory="${CHROME_PROFILE_DIRECTORY}" \
  --no-first-run \
  --no-default-browser-check \
  "${IDENTITY_PAGE_URL}"

READY=0
for ((i=0; i<READY_RETRIES; i++)); do
  if "${PYTHON_BIN}" - <<'PY' "${CHROME_REMOTE_DEBUG_PORT}" >/dev/null 2>&1
import json
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as response:
    json.load(response)
PY
  then
    READY=1
    break
  fi
  sleep 1
done

if [[ "${READY}" != "1" ]]; then
  echo "DealWatch Chrome launcher failed: dedicated Chrome did not expose a CDP listener on port ${CHROME_REMOTE_DEBUG_PORT}." >&2
  exit 1
fi

ENSURE_JSON="$("${PYTHON_BIN}" "${ENSURE_TABS_SCRIPT}" --env-file "${ENV_FILE}" --json)"

echo "DealWatch Chrome launcher: launched dedicated Chrome instance for ${CHROME_PROFILE_NAME} (${CHROME_PROFILE_DIRECTORY}) on port ${CHROME_REMOTE_DEBUG_PORT}."
print_lane_summary "${ENSURE_JSON}"
