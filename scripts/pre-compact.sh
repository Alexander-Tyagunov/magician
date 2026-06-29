#!/usr/bin/env bash
# PreCompact hook — capture a high-fidelity resume capsule before compaction.
#
# PreCompact can only BLOCK compaction (not steer or inject context), so we use it
# purely to CAPTURE: bin/ctx writes a structured capsule (goal, open threads, decisions,
# changed files, artifact paths, recent learnings) to a global per-project store and arms
# re-injection for the next prompt (and on resume). Re-injection happens in pattern-detect
# (UserPromptSubmit) and session-start — the events that actually support additionalContext.
# Works WITHOUT a .workspace/ (unlike the old stub); degrades silently on any error.

set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
INPUT=$(cat 2>/dev/null || printf '{}')

{ read -r SID; read -r TPATH; read -r TRIG; } < <(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get('session_id', 'default') or 'default')
print(d.get('transcript_path', '') or '')
print(d.get('trigger', 'manual') or 'manual')
" 2>/dev/null) || { SID=default; TPATH=""; TRIG=manual; }

"$PLUGIN_ROOT/bin/ctx" capsule --session "${SID:-default}" --transcript "${TPATH:-}" \
  --trigger "${TRIG:-manual}" >/dev/null 2>&1 || true

exit 0
