#!/usr/bin/env bash
# SubagentStart / SubagentStop hook — logs agent lifecycle events.
# Usage: agent-lifecycle.sh start|stop

set -euo pipefail

EVENT="${1:-unknown}"
WORKSPACE_LOCAL=".workspace/local"
LOG_FILE="$WORKSPACE_LOCAL/agent-log.json"

mkdir -p "$WORKSPACE_LOCAL"

INPUT=$(cat)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Payload ($INPUT) on STDIN (not python argv): a large subagent payload can trip an
# argv limit and abort the hook under `set -e`. Small args stay as argv.
PYCODE=""; IFS= read -r -d '' PYCODE <<'PYEOF' || true
import json, os, sys

log_file, event, timestamp = sys.argv[1], sys.argv[2], sys.argv[3]
raw_input = sys.stdin.read()

try:
    inp = json.loads(raw_input)
except Exception:
    inp = {}

task = ""
if isinstance(inp, dict):
    task = inp.get("task", inp.get("description", inp.get("agent_id", "")))

entry = {"event": event, "timestamp": timestamp, "task": str(task)[:200]}

existing = []
if os.path.exists(log_file):
    try:
        with open(log_file) as f:
            existing = json.load(f)
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []

existing.append(entry)
existing = existing[-100:]

with open(log_file, "w") as f:
    json.dump(existing, f, indent=2)
PYEOF
printf '%s' "$INPUT" | python3 -c "$PYCODE" "$LOG_FILE" "$EVENT" "$TIMESTAMP" || true
