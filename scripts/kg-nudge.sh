#!/usr/bin/env bash
# PreToolUse(Read|Grep|Glob|Bash) — steer retrieval toward the knowledge graph at the moment
# Claude reaches for a broad grep / whole-file read (where the wasteful, prompt-spammy habit forms):
#   * index EXISTS for this repo  → nudge `kg query/blast/neighbors` (targeted file:line, fewer tokens,
#                                   shared across agents, and uses the ALLOWED Grep/kg tools not raw Bash).
#   * NO index                    → nudge `kg init` (or `cd <repo> && kg init` for other repos) so the
#                                   session stops grinding grep/read across an unindexed tree.
# Catches BOTH the Grep/Read/Glob tools AND raw Bash searches (grep/rg/find/cat/head/tail) — the
# latter is how workflows sneak past the nudge and bombard the owner with read approvals.
#
# Stays SILENT on ranged Reads (offset/limit — already targeted), non-code files, and commands that
# already use kg / the magician CLIs. Throttled + effort-aware. Never blocks the tool.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
INPUT=$(cat 2>/dev/null || printf '{}')

CAP=3
case "${CLAUDE_EFFORT:-}" in low) CAP=1 ;; xhigh|max) CAP=4 ;; esac

DECIDE=$(printf '%s' "$INPUT" | python3 -c "
import json, sys, os, re
try:
    d = json.load(sys.stdin)
except Exception:
    print('skip default'); raise SystemExit
tn = d.get('tool_name', ''); ti = d.get('tool_input', {}) or {}
sid = d.get('session_id') or 'default'
CODE = {'.py','.js','.jsx','.ts','.tsx','.mjs','.cjs','.go','.rs','.rb','.java','.kt','.swift',
        '.scala','.c','.cc','.cpp','.h','.hpp','.cs','.php','.vue','.svelte'}
action='skip'
if tn in ('Grep','Glob'):
    action='nudge'
elif tn == 'Read':
    if ti.get('offset') is None and ti.get('limit') is None:
        ext=os.path.splitext(ti.get('file_path','') or '')[1].lower()
        if ext in CODE: action='nudge'
elif tn == 'Bash':
    cmd = ti.get('command','') or ''
    # already using kg / magician CLIs, or writing → not a nudge target
    if re.search(r'\\bkg\\b|\\bjira\\b|\\bconfluence\\b|\\bctx\\b', cmd) or '>' in cmd:
        action='skip'
    # broad code search or whole-file read via the shell
    elif re.search(r'\\b(grep|rg|ag|ack)\\b|\\bgit\\s+grep\\b|\\bfind\\b', cmd) or re.search(r'\\b(cat|head|tail|less|more)\\b', cmd):
        action='nudge'
print(action, sid)
" 2>/dev/null || echo "skip default")
ACTION=${DECIDE%% *}; SID=${DECIDE##* }
[ "$ACTION" = "nudge" ] || exit 0

MARK="$PLUGIN_DATA/ctx/${SID}.kgnudge"
N=$(cat "$MARK" 2>/dev/null || echo 0)
[ "$N" -ge "$CAP" ] 2>/dev/null && exit 0

MH="${MAGICIAN_HOME:-$HOME/.claude/magician}"
META=$(python3 -c "
import hashlib, os, subprocess
try:
    root = subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,text=True,timeout=5).stdout.strip() or os.getcwd()
except Exception:
    root = os.getcwd()
h = hashlib.sha256(os.path.realpath(root).encode()).hexdigest()[:12]
print(os.path.join('$MH','knowledge-graph','repos',h,'meta.json'))" 2>/dev/null)

mkdir -p "$(dirname "$MARK")"; echo "$((N+1))" > "$MARK"

if [ -n "$META" ] && [ -f "$META" ]; then
  MSG='This repo has a knowledge-graph index. For locating code, prefer kg query "<terms>" / kg blast <file> / kg neighbors <symbol> — exact file:line in far fewer tokens than a broad grep or whole-file read, using the allowed Grep/kg tools (no per-file approval churn), shared across agents. kg refresh if stale. (ranged Read of specific lines is fine.)'
  [ "$N" -ge 1 ] && MSG="Reminder — reach for the knowledge graph before grepping or reading whole files. $MSG"
else
  MSG='No knowledge-graph index for this repo — you are about to grep/read a whole tree the slow, prompt-heavy way. Build one once with `kg init` (then `kg query "<terms>"` / `kg blast <file>` for targeted file:line). Working across multiple repos? index each: `cd <repo> && kg init`. It is the plugin'"'"'s core retrieval path — cheaper, faster, shared, and it uses the allowed Grep/kg tools instead of raw Bash searches that each prompt.'
fi

python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': '[MAGICIAN] '+sys.argv[1]}}))" "$MSG"
exit 0
