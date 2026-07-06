#!/usr/bin/env bash
# PreToolUse(Read|Grep|Glob) — when a knowledge-graph index EXISTS for this repo, nudge
# toward `kg query/blast/neighbors` at the moment Claude reaches for grep or a whole-file
# read (where the wasteful habit forms), so retrieval is targeted and shared across agents.
#
# For Read specifically: stay SILENT on ranged reads (offset/limit — the good, kg-driven
# pattern we want) and on non-code files; only nudge whole-file code reads. Throttled +
# effort-aware ($CLAUDE_EFFORT). Silent if there's no index. Never blocks the tool.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
INPUT=$(cat 2>/dev/null || printf '{}')

# Effort-aware cap: quieter at low effort, a little more insistent at high/xhigh.
CAP=3
case "${CLAUDE_EFFORT:-}" in low) CAP=1 ;; xhigh|max) CAP=4 ;; esac

# Decide eligibility from the tool + input (skip ranged/non-code Reads), get session id.
DECIDE=$(printf '%s' "$INPUT" | python3 -c "
import json, sys, os
try:
    d = json.load(sys.stdin)
except Exception:
    print('skip default'); raise SystemExit
tn = d.get('tool_name', '')
ti = d.get('tool_input', {}) or {}
sid = d.get('session_id') or 'default'
CODE = {'.py','.js','.jsx','.ts','.tsx','.mjs','.cjs','.go','.rs','.rb','.java','.kt','.swift',
        '.scala','.c','.cc','.cpp','.h','.hpp','.cs','.php','.vue','.svelte'}
skip = False
if tn == 'Read':
    if ti.get('offset') or ti.get('limit'):
        skip = True  # ranged read = already targeted (often kg-driven) → don't nag
    else:
        ext = os.path.splitext(ti.get('file_path', '') or '')[1].lower()
        if ext not in CODE:
            skip = True  # non-code file → grep/read is fine
print(('skip' if skip else 'nudge'), sid)
" 2>/dev/null || echo "skip default")
ACTION=${DECIDE%% *}; SID=${DECIDE##* }
[ "$ACTION" = "nudge" ] || exit 0

# Throttle FIRST (cheap).
MARK="$PLUGIN_DATA/ctx/${SID}.kgnudge"
N=$(cat "$MARK" 2>/dev/null || echo 0)
[ "$N" -ge "$CAP" ] 2>/dev/null && exit 0

# Index present for this repo? (repohash must match bin/kg's sha256 scheme)
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

# Escalate wording after the first nudge.
BASE='This repo has a knowledge-graph index. For locating code, prefer kg query "<terms>" / kg blast <file> / kg neighbors <symbol> — it returns the exact file:line in far fewer tokens than a broad grep or whole-file read, and is shared across agents. Run kg refresh first if results look stale. (grep and ranged Read of specific lines are still fine.)'
[ "$N" -ge 1 ] && BASE="Reminder — reach for the knowledge graph before grepping or reading whole files. $BASE"

python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': '[MAGICIAN] '+sys.argv[1]}}))" "$BASE"
exit 0
