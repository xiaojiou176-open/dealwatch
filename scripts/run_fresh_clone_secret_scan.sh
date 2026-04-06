#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCAN_REF="HEAD"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      SCAN_REF="${2:?missing ref value}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--ref <git-ref>]" >&2
      exit 2
      ;;
  esac
done

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "Fresh-clone secret scan refused: gitleaks is not installed." >&2
  exit 1
fi

if ! command -v trufflehog >/dev/null 2>&1; then
  echo "Fresh-clone secret scan refused: trufflehog is not installed." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

clone_dir="${tmp_dir}/dealwatch-fresh-clone"

git clone --quiet "file://${ROOT}" "${clone_dir}"
git -C "${clone_dir}" checkout --quiet "${SCAN_REF}"

(
  cd "${clone_dir}"
  gitleaks git . --no-banner --redact
  trufflehog git --no-update --fail "file://${clone_dir}"
)
