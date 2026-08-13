#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cleanup() {
  jobs -pr | xargs -r kill
}
trap cleanup EXIT INT TERM
"${SCRIPT_DIR}/dev-backend.sh" &
"${SCRIPT_DIR}/dev-frontend.sh" &
wait
