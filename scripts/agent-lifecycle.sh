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

python3 - "$LOG_FILE" "$EVENT" "$TIMESTAMP" "$INPUT" <<'PYEOF'
import json, os, sys

log_file, event, timestamp, raw_input = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

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
