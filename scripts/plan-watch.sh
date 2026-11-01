#!/usr/bin/env bash
# Monitor plan-watch (starts the first time the user runs /magician:blueprint in a session).
# Every 2 s it looks at the reviewer event log of the newest live plan — the events.jsonl under
# .workspace/local/plans/<plan>/state/ with the latest change, or the folder MAGICIAN_PLAN_STATE
# names — and prints each line added since the last check as one `plan-event: ` line, control
# characters removed and the payload cut at 2,048 bytes. Lines present before the first check are
# not printed; the byte offset is kept in plan-watch.offset next to the log, so a later watch of the
# same plan resumes where this one stopped. Stops after 3 h (MAGICIAN_PLAN_WATCH_MAX_SECONDS
# shortens that), when state.json in the same folder says the plan is approved or rejected, or at
# session end. Prints nothing else. Plain bash; always exits 0.
export LC_ALL=C

MAX=${MAGICIAN_PLAN_WATCH_MAX_SECONDS:-10800}
case "$MAX" in ''|*[!0-9]*) MAX=10800 ;; esac
PINNED=${MAGICIAN_PLAN_STATE:-}

# Prints the path of the event log to follow (empty while no plan has one).
locate() {
  if [ -n "$PINNED" ]; then
    [ -f "$PINNED/events.jsonl" ] && printf '%s\n' "$PINNED/events.jsonl"
    return 0
  fi
  ls -t .workspace/local/plans/*/state/events.jsonl 2>/dev/null | head -n 1
  return 0
}

# Prints the byte offset of the end of the last complete line of $1 (0 when the file is missing).
complete_end() {
  local size tail_bytes
  [ -f "$1" ] || { echo 0; return 0; }
  size=$(wc -c < "$1" | tr -d ' ')
  [ "$size" -gt 0 ] || { echo 0; return 0; }
  if [ "$(tail -c 1 "$1" | wc -l | tr -d ' ')" = 1 ]; then
    echo "$size"
  else
    tail_bytes=$(tail -n 1 "$1" | wc -c | tr -d ' ')
    echo $((size - tail_bytes))
  fi
  return 0
}

# True when state.json beside the log says the review is over.
finished() {
  local state="${1%/*}/state.json"
  [ -f "$state" ] || return 1
  grep -Eq '"status"[[:space:]]*:[[:space:]]*"(approved|rejected)"' "$state"
}

LOG=""; OFF=0; SIDECAR=""
SECONDS=0
while [ "$SECONDS" -lt "$MAX" ]; do
  NEW=$(locate)
  if [ -z "$NEW" ]; then
    sleep 2
    continue
  fi
  if [ "$NEW" != "$LOG" ]; then                      # first sighting, or a newer plan took over
    LOG=$NEW
    SIDECAR="${LOG%/*}/plan-watch.offset"
    OFF=""
    [ -f "$SIDECAR" ] && OFF=$(tr -cd '0-9' < "$SIDECAR")
    [ -n "$OFF" ] || OFF=$(complete_end "$LOG")      # no record: start after what is already there
  fi
  END=$(complete_end "$LOG")
  if [ "$END" -lt "$OFF" ]; then OFF=0; fi           # the log was replaced: read it from the start
  if [ "$END" -gt "$OFF" ]; then
    tail -c +$((OFF + 1)) "$LOG" | head -c $((END - OFF)) \
      | tr -d '\000-\011\013-\037\177' | sed '/^$/d' | cut -c 1-2048 | sed 's/^/plan-event: /'
    OFF=$END
    printf '%s\n' "$OFF" > "$SIDECAR" 2>/dev/null
  fi
  if finished "$LOG"; then
    exit 0
  fi
  sleep 2
done
exit 0
