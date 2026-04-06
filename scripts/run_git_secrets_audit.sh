#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN_FILE="$ROOT/scripts/git_secrets_patterns.txt"

if ! command -v git-secrets >/dev/null 2>&1; then
  echo "ERROR: git-secrets is not installed." >&2
  exit 1
fi

if [ ! -f "$PATTERN_FILE" ]; then
  echo "ERROR: missing pattern file: $PATTERN_FILE" >&2
  exit 1
fi

MODE="${1:---scan}"

case "$MODE" in
  --scan|--scan-history)
    ;;
  *)
    echo "Usage: $0 [--scan|--scan-history]" >&2
    exit 1
    ;;
esac

CMD=(git)

while IFS= read -r pattern || [ -n "$pattern" ]; do
  if [ -z "$pattern" ] || [[ "$pattern" =~ ^# ]]; then
    continue
  fi
  CMD+=(-c "secrets.patterns=$pattern")
done < "$PATTERN_FILE"

CMD+=(secrets "$MODE")

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

git clone -q "$ROOT" "$TMPDIR/repo"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.runtime-cache' \
  --exclude '.pytest_cache' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude 'dist' \
  --exclude 'build' \
  "$ROOT/" "$TMPDIR/repo/"
cd "$TMPDIR/repo"
"${CMD[@]}"
