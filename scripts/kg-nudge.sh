#!/usr/bin/env bash
# PreToolUse(Grep|Glob) — when a knowledge-graph index EXISTS for this repo, nudge
# toward `kg query/blast/neighbors` at the moment Claude reaches for grep (the point
# where the habit actually forms). Throttled to a few per session so it sets the habit
# without nagging. Silent if there's no index. Never blocks the tool.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
INPUT=$(cat 2>/dev/null || printf '{}')

SID=$(printf '%s' "$INPUT" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('session_id') or 'default')
except Exception: print('default')" 2>/dev/null || echo default)

# Throttle FIRST (cheap) — after the cap, do nothing further.
MARK="$PLUGIN_DATA/ctx/${SID}.kgnudge"
N=$(cat "$MARK" 2>/dev/null || echo 0)
[ "$N" -ge 3 ] 2>/dev/null && exit 0

# Index present for this repo? (stat the meta; repohash must match bin/kg's scheme)
MH="${MAGICIAN_HOME:-$HOME/.claude/magician}"
META=$(python3 -c "
import hashlib, os, subprocess
try:
    root = subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,text=True,timeout=5).stdout.strip() or os.getcwd()
except Exception:
    root = os.getcwd()
h = hashlib.sha256(os.path.realpath(root).encode()).hexdigest()[:12]
print(os.path.join('$MH','knowledge-graph','repos',h,'meta.json'))" 2>/dev/null)
[ -n "$META" ] && [ -f "$META" ] || exit 0   # no index → stay silent

mkdir -p "$(dirname "$MARK")"; echo "$((N+1))" > "$MARK"

python3 -c "import json; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': '[MAGICIAN] This repo has a knowledge-graph index. For locating code, prefer kg query \"<terms>\" / kg blast <file> / kg neighbors <symbol> — it returns the exact file:line in far fewer tokens than a broad grep, and is shared across agents. Run kg refresh first if results look stale. (grep is still fine for non-code or literal-string scans.)'}}))"
exit 0
