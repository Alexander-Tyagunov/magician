#!/usr/bin/env bash
# SubagentStop hook (matcher "^magician:"): when one of magician's own agents finishes, records its
# final status in .workspace/local/obstacles.jsonl: BLOCKED or DEGRADED with the obstacle text, or
# CLEAN (empty obstacle) for STATUS: DONE. The /chronicle and /manifest roll-ups read it; /chronicle
# consolidate counts the CLEAN rows. This is the one hook that reads a transcript, and only the
# agent's own: the last 4 KiB of the file named by the event's transcript path (the agent transcript
# path when the event carries one), only to look for "STATUS: BLOCKED", "STATUS: DEGRADED" or
# "STATUS: DONE"; nothing else from it is kept. It writes only when the project has a .workspace
# folder (set up by /almanac, whose .gitignore entry keeps .workspace/local/ out of commits).
# Plain bash 3.2; always exits 0.
export LC_ALL=C

INPUT=""; [ ! -t 0 ] && INPUT=$(head -c65536 2>/dev/null | tr -d '\n\r')
[ -n "$INPUT" ] || exit 0
[ -d ".workspace" ] || exit 0

_field() {  # $1=key -> raw string value of the first "key": "value" pair, or nothing
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  if [[ $INPUT =~ $re ]]; then printf '%s' "${BASH_REMATCH[1]}"; fi
}
_json_str() {  # escape for a JSON string body; control bytes are dropped
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\t'/ }
  printf '%s' "$s" | tr -d '\000-\037\177'
}

AGENT=$(_field agent_type)
case "$AGENT" in magician:*) ;; *) exit 0 ;; esac
case "$AGENT" in *[!A-Za-z0-9:_-]*) exit 0 ;; esac
AGENT=${AGENT:0:64}

PATH_RAW=$(_field agent_transcript_path)
[ -n "$PATH_RAW" ] || PATH_RAW=$(_field transcript_path)
[ -n "$PATH_RAW" ] || exit 0
case "$PATH_RAW" in *\\*) exit 0 ;; esac   # an escaped path is not a plain file name
case "$PATH_RAW" in /*|[A-Za-z]:*) ;; *) exit 0 ;; esac
[ -f "$PATH_RAW" ] || exit 0

TAIL=$(tail -c 4096 "$PATH_RAW" 2>/dev/null | tr -d '\000')
[ -n "$TAIL" ] || exit 0

# The last status marker in the tail, and the text that follows it on the same line (a transcript
# line is JSON, so the text ends at the next quote or backslash).
STATUS=""; OBSTACLE=""
re_status='STATUS: (BLOCKED|DEGRADED|DONE)[] :-]*([^"\\]{0,255})'
t=$TAIL
while [[ $t =~ $re_status ]]; do
  m=${BASH_REMATCH[0]}
  t=${t#*"$m"}
  if [ "${BASH_REMATCH[1]}" = DONE ]; then   # DONE_WITH_... is not a clean DONE
    case "${m#STATUS: DONE}" in [A-Za-z0-9_]*) continue ;; esac
  fi
  STATUS=${BASH_REMATCH[1]}
  OBSTACLE=${BASH_REMATCH[2]}
done
[ -n "$STATUS" ] || exit 0
[ "$STATUS" = DONE ] && { STATUS=CLEAN; OBSTACLE=""; }
OBSTACLE=$(printf '%s' "$OBSTACLE" | tr -s '[:space:]' ' ')
OBSTACLE=${OBSTACLE# }; OBSTACLE=${OBSTACLE% }

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LINE=$(printf '{"ts":"%s","agent":"%s","status":"%s","obstacle":"%s"}' "$TS" "$(_json_str "$AGENT")" "$STATUS" "$(_json_str "$OBSTACLE")")
while [ ${#LINE} -gt 1000 ] && [ ${#OBSTACLE} -gt 20 ]; do   # at most 1 KB per record: shorten the obstacle text
  OBSTACLE=${OBSTACLE:0:${#OBSTACLE}-20}
  LINE=$(printf '{"ts":"%s","agent":"%s","status":"%s","obstacle":"%s"}' "$TS" "$(_json_str "$AGENT")" "$STATUS" "$(_json_str "$OBSTACLE")")
done

mkdir -p .workspace/local 2>/dev/null || exit 0
printf '%s\n' "$LINE" >> .workspace/local/obstacles.jsonl 2>/dev/null
exit 0
