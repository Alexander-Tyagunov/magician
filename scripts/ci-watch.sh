#!/usr/bin/env bash
# Monitor ci-watch (starts the first time the user runs /magician:deploy in a session).
# Every 90 s it asks the GitHub CLI, with the user's existing `gh` login, for the newest FAILED
# GitHub Actions run on the current branch. The first successful check only records a baseline, so a
# failure that predates the watch is never reported. Each later new failure prints one line with the
# run ID only (no run titles or other text from GitHub). Stops after 120 checks (about 3 hours)
# or at session end. Prints nothing when gh, a git repository, an origin remote or a branch is missing.
# Nothing is stored. Plain bash; always exits 0.
export LC_ALL=C
command -v gh >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0
BRANCH=$(git symbolic-ref --short -q HEAD 2>/dev/null)
[ -n "$BRANCH" ] || exit 0

# Prints the newest failed run ID (empty when the branch has none); returns 1 when gh fails,
# so an unreachable or logged-out gh never counts as "no failures".
latest() {
  local out
  out=$(gh run list --branch "$BRANCH" --status failure --limit 1 --json databaseId 2>/dev/null) || return 1
  printf '%s' "$out" | grep -oE '"databaseId"[[:space:]]*:[[:space:]]*[0-9]+' | head -n 1 | grep -oE '[0-9]+$'
  return 0
}

POLLS=120
BASE=0; SEEN=""
if ID=$(latest); then BASE=1; SEEN=$ID; fi   # check 1: silent baseline
i=1
while [ "$i" -lt "$POLLS" ]; do              # checks 2..120, 90 s apart
  sleep 90
  i=$((i + 1))
  ID=$(latest) || continue
  if [ "$BASE" = 0 ]; then                   # no baseline yet (gh failed so far): take it silently
    BASE=1; SEEN=$ID
    continue
  fi
  [ -n "$ID" ] || continue
  if [ -z "$SEEN" ] || [ "$ID" -gt "$SEEN" ]; then   # run IDs only grow
    SEEN=$ID
    echo "magician ci-watch: GitHub Actions run $ID on the current branch finished with status failure."
  fi
done
exit 0
