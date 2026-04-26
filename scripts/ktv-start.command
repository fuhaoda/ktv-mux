#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/ktv" ]; then
  scripts/bootstrap_mac.sh
fi

URL="${KTV_URL:-http://127.0.0.1:8000}"
PORT="${KTV_PORT:-8000}"

echo "Running ktv doctor before startup..."
.venv/bin/ktv --library library doctor || true
open "$URL/doctor" >/dev/null 2>&1 || true
.venv/bin/ktv --library library serve --host 127.0.0.1 --port "$PORT"
