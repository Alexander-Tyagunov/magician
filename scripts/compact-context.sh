#!/usr/bin/env bash
# SessionStart hook (matcher "compact"): after a compaction, restates working-state pointers taken
# from git and the .workspace/shared artifact folders: branch, uncommitted files, this session's
# commits and shared artifacts. It reads nothing from the conversation (no transcript, prompt or
# summary) and writes nothing. Plain bash 3.2 + git; no `set -e`/`-u`; always exits 0.
export LC_ALL=C

BUDGET=9500   # additionalContext cap (Claude Code truncates past 10,000 characters)
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
INPUT=""; [ ! -t 0 ] && INPUT=$(head -c65536 2>/dev/null | tr -d '\n\r')

_json_str() {  # escape for a JSON string body; other control bytes are dropped
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\t'/\\t}; s=${s//$'\r'/\\r}; s=${s//$'\n'/\\n}
  printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037'
}
_bullets() {  # stdin lines -> "- line" list (at most $1 lines, then a count of the rest)
  local max=$1 n=0 out="" line
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    n=$((n + 1))
    [ "$n" -le "$max" ] && out="${out}
- ${line}"
  done
  [ "$n" -gt "$max" ] && out="${out}
- (+$((n - max)) more)"
  printf '%s' "$out"
}

ROOT=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
fi
[ -n "$ROOT" ] || ROOT=$(pwd -P 2>/dev/null)

# Session start from the per-session stamp written by session-start.sh (UTC ISO-8601).
START=""
re_sid='"session_id"[[:space:]]*:[[:space:]]*"([A-Za-z0-9_-]+)"'
if [[ $INPUT =~ $re_sid ]] && [ -f "$DATA/sessions/${BASH_REMATCH[1]}.start" ]; then
  read -r START < "$DATA/sessions/${BASH_REMATCH[1]}.start"
fi
re_ts='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'
[[ $START =~ $re_ts ]] || START=""

GIT_PART=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  [ -n "$BRANCH" ] && GIT_PART="
Branch: ${BRANCH}"
  CHANGED=$(git diff --name-only HEAD 2>/dev/null | head -200 | _bullets 15)
  [ -n "$CHANGED" ] && GIT_PART="${GIT_PART}
Uncommitted changes vs HEAD:${CHANGED}"
  LOG=""; LOG_LABEL=""
  if [ -n "$START" ]; then
    LOG=$(git log --since="$START" --pretty='%h %s' 2>/dev/null | head -200 | _bullets 10)
    LOG_LABEL="Commits since this session started (${START})"
  fi
  if [ -z "$LOG" ]; then
    LOG=$(git log -5 --pretty='%h %s' 2>/dev/null | _bullets 5)
    LOG_LABEL="Recent commits"
  fi
  [ -n "$LOG" ] && GIT_PART="${GIT_PART}
${LOG_LABEL}:${LOG}"
fi

ARTS=$(for _d in specs plans research diffs decisions; do
  for _f in "$ROOT/.workspace/shared/$_d"/*; do
    [ -f "$_f" ] && printf '%s\n' ".workspace/shared/$_d/${_f##*/}"
  done
done | _bullets 20)

[ -z "$GIT_PART" ] && [ -z "$ARTS" ] && exit 0

CONTEXT="Context was compacted. Working-state pointers for this directory, read from git and .workspace/shared (for reference):${GIT_PART}"
[ -n "$ARTS" ] && CONTEXT="${CONTEXT}
Shared artifacts in .workspace/shared:${ARTS}"
if [ ${#CONTEXT} -gt "$BUDGET" ]; then   # cut at a line boundary so no UTF-8 sequence is split
  CONTEXT=$(printf '%s' "$CONTEXT" | head -c"$BUDGET" | sed '$d')
fi
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$(_json_str "$CONTEXT")"
exit 0
