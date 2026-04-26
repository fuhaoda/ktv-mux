#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/ktv" ]; then
  scripts/bootstrap_mac.sh
fi

HOST="${KTV_HOST:-127.0.0.1}"
PORT="${KTV_PORT:-8000}"

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

is_ktv_mux() {
  command -v curl >/dev/null 2>&1 && curl -fsS "http://$HOST:$1/doctor" 2>/dev/null | grep -q "ktv-mux"
}

if port_in_use "$PORT"; then
  if is_ktv_mux "$PORT"; then
    URL="http://$HOST:$PORT"
    echo "ktv-mux is already running at $URL"
    open "$URL" >/dev/null 2>&1 || true
    exit 0
  fi
  echo "Port $PORT is busy. Looking for a free local port..."
  for candidate in 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010; do
    if ! port_in_use "$candidate"; then
      PORT="$candidate"
      break
    fi
  done
fi

URL="http://$HOST:$PORT"

echo "Running ktv doctor before startup..."
.venv/bin/ktv --library library doctor || true
open "$URL/doctor" >/dev/null 2>&1 || true
.venv/bin/ktv --library library serve --host "$HOST" --port "$PORT"
