#!/usr/bin/env bash
# Stop the Magician Visual Design Companion
# Usage: vc-stop.sh <design-dir>

DESIGN_DIR="${1:?Usage: vc-stop.sh <design-dir>}"
PID_FILE="$DESIGN_DIR/state/server.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null && echo "stopped (pid $PID)" || echo "process already gone"
  rm -f "$PID_FILE"
else
  echo "not running"
fi
