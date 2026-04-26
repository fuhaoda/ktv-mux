#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$HOME/Desktop/KTV Mux.command"

mkdir -p "$HOME/Desktop"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
cd "$ROOT_DIR"
scripts/ktv-start.command
EOF

chmod +x "$LAUNCHER"
echo "Created $LAUNCHER"
