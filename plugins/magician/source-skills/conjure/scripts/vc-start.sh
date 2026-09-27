#!/usr/bin/env bash
# Start the Magician Visual Design Companion
# Usage: vc-start.sh <design-dir> <project-name>
#
# Screens stay in <design-dir> (e.g. .workspace/shared/designs/<date>-<feature>). The companion's
# runtime state — click/chat event log, outbox, pid and server-info — goes to the matching folder
# under .workspace/local/ (always gitignored), so companion chat never lands in the shared tree.

set -euo pipefail

DESIGN_DIR="${1:?Usage: vc-start.sh <design-dir> <project-name>}"
PROJECT_NAME="${2:?Missing project-name}"
DESIGN_DIR="${DESIGN_DIR%/}"

case "$DESIGN_DIR" in
  *.workspace/shared/*) STATE_DIR="${DESIGN_DIR%%.workspace/shared/*}.workspace/local/${DESIGN_DIR#*.workspace/shared/}/state" ;;
  *) STATE_DIR="$DESIGN_DIR/state" ;;
esac

mkdir -p "$DESIGN_DIR/screens" "$DESIGN_DIR/screenshots" "$STATE_DIR"
# Keep the state folder out of git even when .workspace/local/ is not in .gitignore yet.
[ -e "$STATE_DIR/.gitignore" ] || printf '*\n' > "$STATE_DIR/.gitignore"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$STATE_DIR/server.pid"
SERVER_INFO="$STATE_DIR/server-info"

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

node "$SCRIPT_DIR/server.cjs" "$DESIGN_DIR" "$PROJECT_NAME" "$STATE_DIR" &
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
