#!/usr/bin/env -S -u LD_LIBRARY_PATH bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/stop-dev.sh"
exec "${SCRIPT_DIR}/dev.sh"
