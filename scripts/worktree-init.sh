#!/usr/bin/env bash
# WorktreeCreate hook — copies workspace context into new worktrees.

set -euo pipefail

INPUT=$(cat)

# Payload on STDIN (not python argv) — a large hook payload can trip an argv limit
# and abort the hook under `set -e`.
WORKTREE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get("worktree_path", d.get("path", "")))
except Exception:
    pass') || WORKTREE_PATH=""

[ -z "$WORKTREE_PATH" ] && exit 0
[ -d "$WORKTREE_PATH" ] || exit 0

SRC_LOCAL=".workspace/local"
DST_LOCAL="$WORKTREE_PATH/.workspace/local"

[ -d "$SRC_LOCAL" ] || exit 0

mkdir -p "$DST_LOCAL"

[ -f "$SRC_LOCAL/prefs.md" ]   && cp "$SRC_LOCAL/prefs.md"   "$DST_LOCAL/prefs.md"
[ -f "$SRC_LOCAL/session.md" ] && cp "$SRC_LOCAL/session.md" "$DST_LOCAL/session.md"

GITIGNORE="$WORKTREE_PATH/.gitignore"
if ! grep -q "\.workspace/local" "$GITIGNORE" 2>/dev/null; then
  echo ".workspace/local/" >> "$GITIGNORE"
fi
