#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${WEB_ROOT}/frontend"
exec pnpm exec vite --host 0.0.0.0 --port "${A1Z_WEB_FRONTEND_PORT:-5173}" --strictPort
