#!/usr/bin/env bash
# Stop hook — writes a structured session learning entry using observable data.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
CHRONICLE_DIR="$PLUGIN_DATA/chronicle"
START_TIME_FILE="$PLUGIN_DATA/session-start-time.txt"

mkdir -p "$CHRONICLE_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATESTAMP=$(date -u +"%Y-%m-%d-%H-%M")
ENTRY_FILE="$CHRONICLE_DIR/$DATESTAMP.json"

SESSION_START=""
[ -f "$START_TIME_FILE" ] && SESSION_START=$(cat "$START_TIME_FILE")

WORKING_DIR=$(pwd)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "no-git")
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null | head -20 || echo "")
STAGED_FILES=$(git diff --name-only --cached 2>/dev/null | head -20 || echo "")

GIT_LOG=""
if [ -n "$SESSION_START" ] && git rev-parse HEAD &>/dev/null 2>&1; then
  GIT_LOG=$(git log --oneline --since="$SESSION_START" 2>/dev/null | head -10 || echo "")
fi

COMMIT_COUNT=0
if [ -n "$GIT_LOG" ]; then
  COMMIT_COUNT=$(echo "$GIT_LOG" | grep -c . 2>/dev/null || echo "0")
fi

if [ -n "$GIT_LOG" ]; then
  SUMMARY="$COMMIT_COUNT commit(s) on $BRANCH"
elif [ -n "$CHANGED_FILES" ]; then
  SUMMARY="Modified files on $BRANCH: $(echo "$CHANGED_FILES" | head -3 | tr '\n' ', ')"
else
  SUMMARY="Session in $WORKING_DIR on branch $BRANCH"
fi

python3 - "$ENTRY_FILE" "$TIMESTAMP" "$SESSION_START" "$WORKING_DIR" "$BRANCH" "$COMMIT_COUNT" "$SUMMARY" <<'PYEOF'
import json, sys

entry_file, timestamp, session_start, working_dir, branch, commits, summary = sys.argv[1:8]

entry = {
    "timestamp": timestamp,
    "session_start": session_start,
    "working_dir": working_dir,
    "branch": branch,
    "commits": commits,
    "summary": summary
}

with open(entry_file, "w") as f:
    json.dump(entry, f, indent=2)

print(f"Chronicle written: {entry_file}", file=sys.stderr)
PYEOF

rm -f "$START_TIME_FILE"
