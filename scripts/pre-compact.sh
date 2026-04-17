#!/usr/bin/env bash
# PreCompact hook — saves observable session state to workspace before compaction.

set -euo pipefail

WORKSPACE_LOCAL=".workspace/local"
SESSION_FILE="$WORKSPACE_LOCAL/session.md"

[ -d "$WORKSPACE_LOCAL" ] || exit 0

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
CHANGED=$(git diff --name-only HEAD 2>/dev/null | head -10 || echo "none")
STAGED=$(git diff --name-only --cached 2>/dev/null | head -10 || echo "none")

cat > "$SESSION_FILE" <<SESSION
# Session State — saved at compaction

**Timestamp:** $TIMESTAMP
**Branch:** $BRANCH

## Modified files (unstaged)
$CHANGED

## Staged files
$STAGED

## Notes
Context was compacted. Resume by checking git status and recent git log.
SESSION
