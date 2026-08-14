#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  trap - EXIT INT TERM
  for pid in "${BACKEND_PID}" "${FRONTEND_PID}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"${SCRIPT_DIR}/dev-backend.sh" &
BACKEND_PID=$!

# Bind/configuration failures (most commonly an old server still owning port
# 8000) happen immediately. Do not start a frontend that can only display a
# permanently pending UI.
sleep 0.8
if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
  wait "${BACKEND_PID}" || status=$?
  echo "A1Z Web backend failed to start. Check whether port ${A1Z_WEB_PORT:-8000} is already in use." >&2
  exit "${status:-1}"
fi

"${SCRIPT_DIR}/dev-frontend.sh" &
FRONTEND_PID=$!

set +e
wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
status=$?
set -e
echo "A1Z Web development service exited (status ${status}); stopping the paired service." >&2
exit "${status}"
