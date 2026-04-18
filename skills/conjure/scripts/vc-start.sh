#!/usr/bin/env bash
# Start the Magician Visual Design Companion
# Usage: vc-start.sh <design-dir> <project-name>

set -euo pipefail

DESIGN_DIR="${1:?Usage: vc-start.sh <design-dir> <project-name>}"
PROJECT_NAME="${2:?Missing project-name}"

mkdir -p "$DESIGN_DIR/screens" "$DESIGN_DIR/state" "$DESIGN_DIR/screenshots"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DESIGN_DIR/state/server.pid"
SERVER_INFO="$DESIGN_DIR/state/server-info"

# Kill stale server if running
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  kill "$OLD_PID" 2>/dev/null || true
  rm -f "$PID_FILE" "$SERVER_INFO"
fi

if ! command -v node &>/dev/null; then
  echo '{"error":"node not found — install Node.js to use the visual companion"}' >&2
  exit 1
fi

node "$SCRIPT_DIR/server.cjs" "$DESIGN_DIR" "$PROJECT_NAME" &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# Wait up to 3s for server-info
for i in $(seq 1 30); do
  if [ -f "$SERVER_INFO" ]; then
    cat "$SERVER_INFO"
    exit 0
  fi
  sleep 0.1
done

echo '{"error":"server did not start in time"}' >&2
kill "$SERVER_PID" 2>/dev/null || true
exit 1
