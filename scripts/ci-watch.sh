#!/usr/bin/env bash
# magician CI watcher — a Claude Tag-style proactive watcher.
# Started on the first /deploy invocation (see monitors/monitors.json). Polls GitHub
# Actions for the most recent FAILED run on this repo and emits one line when a new
# failure appears, so Claude can react without being asked to watch.
# Exits quietly (no output) if gh, a git repo, or an origin remote is absent.

set -uo pipefail

command -v gh >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

SEEN=""
while true; do
  RUN=$(gh run list --status failure --limit 1 \
        --json databaseId,displayTitle,headBranch \
        --jq '.[0] | "\(.databaseId) [\(.headBranch)] \(.displayTitle)"' 2>/dev/null || true)
  if [ -n "$RUN" ] && [ "$RUN" != "null" ]; then
    ID="${RUN%% *}"
    if [ "$ID" != "$SEEN" ]; then
      SEEN="$ID"
      echo "CI RED: failed run $RUN — investigate with /unravel or '/deploy fix'."
    fi
  fi
  sleep 90
done
