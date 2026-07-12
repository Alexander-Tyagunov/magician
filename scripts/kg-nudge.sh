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
#
# Performance: this hook fires on EVERY Read/Grep/Glob/Bash, so the hot path is pure bash. Once the
# per-session cap is reached the script exits in a few ms with zero python (the throttle gate below);
# only an actual nudge spawns python — a SINGLE pass that decides, resolves the index path, and emits
# the steer, replacing the previous decide+meta+emit (up to three interpreter starts + a git call).

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
INPUT=$(cat 2>/dev/null || printf '{}')

CAP=3
case "${CLAUDE_EFFORT:-}" in low) CAP=1 ;; xhigh|max) CAP=4 ;; esac

# --- Fast path (pure bash, ZERO subprocess): after CAP nudges this session, every subsequent
#     Read/Grep/Glob/Bash exits here instead of spawning python just to re-run the decision.
#     session_id + counter are read with bash-native matching (no grep/sed/cat exec). ---
SID=default
if [[ "$INPUT" =~ \"session_id\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]]; then SID="${BASH_REMATCH[1]}"; fi
MARK="$PLUGIN_DATA/ctx/${SID}.kgnudge"

N=0; [ -f "$MARK" ] && { read -r N < "$MARK" 2>/dev/null || true; }
[[ "$N" =~ ^[0-9]+$ ]] || N=0
[ "$N" -ge "$CAP" ] && exit 0

# A ranged Read (offset/limit with a NUMERIC value) is already targeted → skip without spawning python.
# Gate on the FIRST (top-level) tool_name match — mirrors python's d.get("tool_name"), so a Bash
# command whose text merely contains "tool_name":"Read" can't trigger it. Requiring a digit after the
# colon mirrors python's `offset is None` test: offset:null / absent still falls through to a nudge, so
# this stays a strict subset of the python "skip" branch (output unchanged either way).
TN=""
[[ "$INPUT" =~ \"tool_name\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]] && TN="${BASH_REMATCH[1]}"
if [ "$TN" = "Read" ] && [[ "$INPUT" =~ \"(offset|limit)\"[[:space:]]*:[[:space:]]*-?[0-9] ]]; then
  exit 0
fi

MH="${MAGICIAN_HOME:-$HOME/.claude/magician}"

# --- Single python pass: decide → (only if this is a nudge target) resolve the index path and emit
#     the steer. INPUT arrives on stdin (no argv size limit — matches the old stdin behaviour on huge
#     commands); mh/n are small argv. hashlib/subprocess are imported lazily only on the nudge branch so
#     the common "reaches python then skips" path pays nothing extra. Nothing is printed for non-nudge
#     calls, so OUT stays empty and the counter is left untouched — same outcome as before. ---
PYCODE=""; IFS= read -r -d '' PYCODE <<'PYEOF' || true
import json, sys, os, re

try:
    d = json.loads(sys.stdin.read())
except Exception:
    raise SystemExit
mh = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    n = int(sys.argv[2])
except Exception:
    n = 0

tn = d.get("tool_name", ""); ti = d.get("tool_input", {}) or {}
CODE = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".rb", ".java", ".kt",
        ".swift", ".scala", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".php", ".vue", ".svelte"}

action = "skip"
if tn in ("Grep", "Glob"):
    action = "nudge"
elif tn == "Read":
    if ti.get("offset") is None and ti.get("limit") is None:
        ext = os.path.splitext(ti.get("file_path", "") or "")[1].lower()
        if ext in CODE:
            action = "nudge"
elif tn == "Bash":
    cmd = ti.get("command", "") or ""
    # already using kg / magician CLIs, or writing → not a nudge target
    if re.search(r'\bkg\b|\bjira\b|\bconfluence\b|\bctx\b', cmd) or '>' in cmd:
        action = "skip"
    # broad code search or whole-file read via the shell
    elif re.search(r'\b(grep|rg|ag|ack)\b|\bgit\s+grep\b|\bfind\b', cmd) or re.search(r'\b(cat|head|tail|less|more)\b', cmd):
        action = "nudge"

if action != "nudge":
    raise SystemExit

import hashlib, subprocess
try:
    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, timeout=5).stdout.strip() or os.getcwd()
except Exception:
    root = os.getcwd()
h = hashlib.sha256(os.path.realpath(root).encode()).hexdigest()[:12]
meta = os.path.join(mh, 'knowledge-graph', 'repos', h, 'meta.json')

if os.path.isfile(meta):
    msg = ('This repo has a knowledge-graph index. For locating code, prefer kg query "<terms>" / '
           'kg blast <file> / kg neighbors <symbol> — exact file:line in far fewer tokens than a broad '
           'grep or whole-file read, using the allowed Grep/kg tools (no per-file approval churn), '
           'shared across agents. kg refresh if stale. (ranged Read of specific lines is fine.)')
    if n >= 1:
        msg = "Reminder — reach for the knowledge graph before grepping or reading whole files. " + msg
else:
    msg = ('No knowledge-graph index for this repo — you are about to grep/read a whole tree the slow, '
           'prompt-heavy way. Build one once with `kg init` (then `kg query "<terms>"` / `kg blast <file>` '
           'for targeted file:line). Working across multiple repos? index each: `cd <repo> && kg init`. '
           "It is the plugin's core retrieval path — cheaper, faster, shared, and it uses the allowed "
           'Grep/kg tools instead of raw Bash searches that each prompt.')

print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': '[MAGICIAN] ' + msg}}))
PYEOF
OUT=$(printf '%s' "$INPUT" | python3 -c "$PYCODE" "$MH" "$N" 2>/dev/null) || OUT=""

[ -n "$OUT" ] || exit 0

mkdir -p "$(dirname "$MARK")"; echo "$((N+1))" > "$MARK"
printf '%s\n' "$OUT"
exit 0
