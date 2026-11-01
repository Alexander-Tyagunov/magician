#!/usr/bin/env bash
# Stop the Magician companion server (design or plan mode)
# Usage: vc-stop.sh <dir>        (the design dir or the plan dir given to vc-start.sh)
# The pid file lives in the state folder vc-start.sh chose (under .workspace/local/ for a
# .workspace/shared/ dir).

DIR="${1:?Usage: vc-stop.sh <dir>}"
DIR="${DIR%/}"

case "$DIR" in
  *.workspace/shared/*) STATE_DIR="${DIR%%.workspace/shared/*}.workspace/local/${DIR#*.workspace/shared/}/state" ;;
  *) STATE_DIR="$DIR/state" ;;
esac
PID_FILE="$STATE_DIR/server.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null && echo "stopped (pid $PID)" || echo "process already gone"
  rm -f "$PID_FILE" "$STATE_DIR/server-info" "$STATE_DIR/server.json"   # no stale port/token on the next start
else
  echo "not running"
fi
