#!/usr/bin/env bash
# Start the Magician companion server (design studio for /conjure, live plan page for /blueprint).
# Usage: vc-start.sh <design-dir> <project-name>          design mode
#        vc-start.sh <plan-dir>   <project-name> --plan   plan mode
#
# Screens or plan files stay in <dir> (e.g. .workspace/shared/designs/<date>-<feature> or
# .workspace/shared/plans/<date>-<feature>). The companion's runtime state — the event log, the
# outbox, pid and server record — goes to the matching folder under .workspace/local/ (always
# gitignored), so companion traffic never lands in the shared tree.
#
# Prints one JSON object on stdout. Design mode: port, project, url_base, latest_url, design_dir,
# screens_dir, state_dir, events_file, outbox_file. Plan mode: pid, port, token, project, url_base,
# plan_url, plan_dir, state_dir, events_file, state_file (the same object is kept as
# <state>/server.json). Exit 1 with {"error":...} on stderr when node is missing or the server
# does not start within 3 s.

set -euo pipefail

DIR=""; PROJECT_NAME=""; PLAN=0
for arg in "$@"; do
  case "$arg" in
    --plan) PLAN=1 ;;
    *) if [ -z "$DIR" ]; then DIR="$arg"; elif [ -z "$PROJECT_NAME" ]; then PROJECT_NAME="$arg"; fi ;;
  esac
done
[ -n "$DIR" ] || { echo "Usage: vc-start.sh <dir> <project-name> [--plan]" >&2; exit 1; }
[ -n "$PROJECT_NAME" ] || { echo "Missing project-name" >&2; exit 1; }
DIR="${DIR%/}"

case "$DIR" in
  *.workspace/shared/*) STATE_DIR="${DIR%%.workspace/shared/*}.workspace/local/${DIR#*.workspace/shared/}/state" ;;
  *) STATE_DIR="$DIR/state" ;;
esac

if [ "$PLAN" = 1 ]; then
  [ -f "$DIR/plan.json" ] || { echo "{\"error\":\"no plan.json in $DIR\"}" >&2; exit 1; }
  mkdir -p "$STATE_DIR"
else
  mkdir -p "$DIR/screens" "$DIR/screenshots" "$STATE_DIR"
fi
# Keep the state folder out of git even when .workspace/local/ is not in .gitignore yet.
[ -e "$STATE_DIR/.gitignore" ] || printf '*\n' > "$STATE_DIR/.gitignore"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$STATE_DIR/server.pid"
SERVER_INFO="$STATE_DIR/server-info"
SERVER_JSON="$STATE_DIR/server.json"

# Kill stale server if running
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  kill "$OLD_PID" 2>/dev/null || true
  rm -f "$PID_FILE" "$SERVER_INFO" "$SERVER_JSON"
fi

if ! command -v node >/dev/null 2>&1; then
  echo '{"error":"node not found — install Node.js to use the visual companion"}' >&2
  exit 1
fi

if [ "$PLAN" = 1 ]; then
  # The server prints its record (pid, port, token, URLs) as one line on stdout and nothing else;
  # that line becomes server.json. Its log goes to stderr.
  : > "$SERVER_JSON"
  node "$SCRIPT_DIR/server.cjs" --plan "$DIR" "$PROJECT_NAME" "$STATE_DIR" > "$SERVER_JSON" 2>/dev/null &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  READY="$SERVER_JSON"
  PATTERN='"state_file"'
else
  node "$SCRIPT_DIR/server.cjs" "$DIR" "$PROJECT_NAME" "$STATE_DIR" &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  READY="$SERVER_INFO"
  PATTERN='"url_base"'
fi

# Wait up to 3s for the server record
i=0
while [ "$i" -lt 30 ]; do
  if [ -s "$READY" ] && grep -q "$PATTERN" "$READY" 2>/dev/null; then
    cat "$READY"
    exit 0
  fi
  sleep 0.1
  i=$((i + 1))
done

echo '{"error":"server did not start in time"}' >&2
kill "$SERVER_PID" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1
