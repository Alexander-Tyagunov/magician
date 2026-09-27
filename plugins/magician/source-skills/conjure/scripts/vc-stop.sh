#!/usr/bin/env bash
# Stop the Magician Visual Design Companion
# Usage: vc-stop.sh <design-dir>
# The pid file lives in the state folder vc-start.sh chose (under .workspace/local/ for a
# .workspace/shared/ design dir).

DESIGN_DIR="${1:?Usage: vc-stop.sh <design-dir>}"
DESIGN_DIR="${DESIGN_DIR%/}"

case "$DESIGN_DIR" in
  *.workspace/shared/*) STATE_DIR="${DESIGN_DIR%%.workspace/shared/*}.workspace/local/${DESIGN_DIR#*.workspace/shared/}/state" ;;
  *) STATE_DIR="$DESIGN_DIR/state" ;;
esac
PID_FILE="$STATE_DIR/server.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null && echo "stopped (pid $PID)" || echo "process already gone"
  rm -f "$PID_FILE"
else
  echo "not running"
fi
