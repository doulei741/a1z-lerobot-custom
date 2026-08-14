#!/usr/bin/env -S -u LD_LIBRARY_PATH bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${WEB_ROOT}"
exec "${WEB_ROOT}/backend/.venv/bin/uvicorn" app.main:app \
  --app-dir "${WEB_ROOT}/backend" --host 127.0.0.1 --port "${A1Z_WEB_PORT:-8000}" \
  --reload --no-access-log --log-level warning
