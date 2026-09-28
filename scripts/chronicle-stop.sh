#!/usr/bin/env bash
# Stop (async) — keeps ONE small history record per session in this plugin's data directory:
# branch, commit count, changed-file names and a one-line summary, all taken from git. No prompt,
# response or transcript content is read. The newest 50 session records are kept.
# Commit subjects that record a decision ("decided", "switched to", ...) are also appended to the
# per-project learnings file. Off when the user sets the `session_history` plugin option to false.
# Plain bash; always exits 0.
export LC_ALL=C
case "${CLAUDE_PLUGIN_OPTION_SESSION_HISTORY:-true}" in false|0|no|off) exit 0 ;; esac

INPUT=$(cat 2>/dev/null) || exit 0
DATA=${CLAUDE_PLUGIN_DATA:-}
if [ -z "$DATA" ]; then
  [ -n "${HOME:-}" ] || exit 0
  DATA="$HOME/.local/share/magician"
fi
re_sid='"session_id"[[:space:]]*:[[:space:]]*"([A-Za-z0-9_-]{1,128})"'
[[ $INPUT =~ $re_sid ]] || exit 0
SID=${BASH_REMATCH[1]}
KEEP=50

json_escape() {
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}; s=${s//$'\r'/\\r}; s=${s//$'\t'/\\t}
  printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037'
}

# Work in the session's project directory when the payload names a plain existing path.
re_cwd='"cwd"[[:space:]]*:[[:space:]]*"([^"\\]+)"'
if [[ $INPUT =~ $re_cwd ]] && [ -d "${BASH_REMATCH[1]}" ]; then cd "${BASH_REMATCH[1]}" 2>/dev/null || exit 0; fi

DIR="$DATA/chronicle"
mkdir -p "$DIR" "$DATA/sessions" 2>/dev/null || exit 0

# Session start time: written at session start; created here when missing (e.g. a resumed session)
# so every Stop in the same session maps to the same record.
re_iso='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
START_FILE="$DATA/sessions/$SID.start"
START=""
[ -s "$START_FILE" ] && read -r START < "$START_FILE"
if ! [[ $START =~ $re_iso ]]; then
  START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s\n' "$START" > "$START_FILE.$$" 2>/dev/null && mv -f "$START_FILE.$$" "$START_FILE" 2>/dev/null
fi
STAMP=${START:0:19}; STAMP=${STAMP//-/}; STAMP=${STAMP//:/}   # 20260927T101500 -> names sort by time
ENTRY="$DIR/${STAMP}Z-$SID.json"

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
WD=$(pwd -P)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || BRANCH="no-git"
[ -n "$BRANCH" ] || BRANCH="no-git"
CHANGED=$(git diff --name-only HEAD 2>/dev/null | head -20)
LOG=$(git log --since="$START" --pretty=%s 2>/dev/null | head -50)
COMMITS=0
if [ -n "$LOG" ]; then
  COMMITS=$(git rev-list --count --since="$START" HEAD 2>/dev/null)
  case $COMMITS in ''|*[!0-9]*) COMMITS=$(printf '%s\n' "$LOG" | wc -l | tr -d ' ') ;; esac
fi
if [ "$COMMITS" -gt 0 ]; then
  SUMMARY="$COMMITS commit(s) on $BRANCH"
elif [ -n "$CHANGED" ]; then
  SUMMARY="Modified files on $BRANCH: $(printf '%s\n' "$CHANGED" | head -3 | tr '\n' ' ')"
  SUMMARY=${SUMMARY% }
else
  SUMMARY="Session in $WD on branch $BRANCH"
fi

FILES_J=""
while IFS= read -r f; do
  [ -n "$f" ] && FILES_J="$FILES_J${FILES_J:+,}\"$(json_escape "$f")\""
done <<< "$CHANGED"
printf '{"timestamp":"%s","session_id":"%s","session_start":"%s","working_dir":"%s","branch":"%s","commits":%s,"changed_files":[%s],"summary":"%s"}\n' \
  "$NOW" "$SID" "$(json_escape "$START")" "$(json_escape "$WD")" "$(json_escape "$BRANCH")" "$COMMITS" "$FILES_J" "$(json_escape "$SUMMARY")" \
  > "$ENTRY.$$" 2>/dev/null && mv -f "$ENTRY.$$" "$ENTRY" 2>/dev/null

# Keep the newest $KEEP session records (names sort chronologically). Only this format is pruned.
set -- "$DIR"/[0-9]*T[0-9]*Z-*.json
if [ -e "$1" ] && [ "$#" -gt "$KEEP" ]; then
  n=$(( $# - KEEP ))
  while [ "$n" -gt 0 ]; do rm -f -- "$1"; shift; n=$((n - 1)); done
fi

# Decision-style commit subjects -> per-project learnings (project key: first 12 hex of md5(pwd -P)).
[ -n "$LOG" ] || exit 0
if command -v md5sum >/dev/null 2>&1; then H=$(printf '%s' "$WD" | md5sum | cut -c1-12)
elif command -v md5 >/dev/null 2>&1; then H=$(printf '%s' "$WD" | md5 -q | cut -c1-12)
elif [ -x /sbin/md5 ]; then H=$(printf '%s' "$WD" | /sbin/md5 -q | cut -c1-12)   # macOS, /sbin not on PATH
else exit 0; fi
case $H in [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;; *) exit 0 ;; esac
LF="$DATA/projects/$H/learnings.jsonl"
mkdir -p "${LF%/*}" 2>/dev/null || exit 0
TS=$(date +%s)
recent=$(tail -n 40 "$LF" 2>/dev/null)
printf '%s\n' "$LOG" \
  | grep -Ei '(^|[^[:alnum:]_])(decided|chose|chosen|prefer|switch(ed)? to|use[ds]? .* over|going with|standardiz)' \
  | while IFS= read -r subj; do
      subj=$(printf '%s' "$subj" | tr '\t' ' ' | tr -s ' ' | cut -c1-240)
      case $subj in                                   # drop a UTF-8 character split by the cut
        *[$'\xc0'-$'\xff']) subj=${subj%?} ;;
        *[$'\xe0'-$'\xff'][$'\x80'-$'\xbf']) subj=${subj%??} ;;
        *[$'\xf0'-$'\xff'][$'\x80'-$'\xbf'][$'\x80'-$'\xbf']) subj=${subj%???} ;;
      esac
      subj=${subj# }; subj=${subj% }
      [ -n "$subj" ] || continue
      fact=$(json_escape "$subj")
      case $recent in *"\"fact\":\"$fact\""*|*"\"fact\": \"$fact\""*) continue ;; esac
      line=$(printf '{"fact":"%s","source":"git","ts":%s}' "$fact" "$TS")
      printf '%s\n' "$line" >> "$LF"
      recent="$recent"$'\n'"$line"
    done
exit 0
