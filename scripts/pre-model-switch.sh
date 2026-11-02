#!/usr/bin/env bash
# PreModelSwitch hook: holds a model switch for confirmation while a security scan is running.
# A flagged turn can be re-run on a safety fallback model and the session then stays on it, which
# would change the model tier in the middle of a /sentinel sweep or a /divine security lens. When
# MAGICIAN_PIN_MODEL=1 is set, or the marker file .workspace/local/security-scan.active exists in
# the current folder, the hook answers with permissionDecision "ask" and the reason; otherwise it
# prints nothing. It reads only the from_model and to_model fields, writes nothing. Plain bash 3.2;
# always exits 0 (a timed-out PreModelSwitch hook blocks the switch, so this one does no work).
export LC_ALL=C

PIN=0
case "${MAGICIAN_PIN_MODEL:-}" in 1|true|yes|on) PIN=1 ;; esac
[ -f ".workspace/local/security-scan.active" ] && PIN=1
[ "$PIN" = 1 ] || exit 0

INPUT=""; [ ! -t 0 ] && INPUT=$(head -c65536 2>/dev/null | tr -d '\n\r')
_field() {  # $1=key -> value when it is a plain model name, or nothing
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"([A-Za-z0-9._:/-]{1,80})\""
  if [[ $INPUT =~ $re ]]; then printf '%s' "${BASH_REMATCH[1]}"; fi
}
FROM=$(_field from_model)
TO=$(_field to_model)
MOVE=""
[ -n "$FROM" ] && [ -n "$TO" ] && MOVE=" ($FROM to $TO)"

REASON="magician: safety fallback would change tier mid-scan${MOVE}; a security scan is active (marker .workspace/local/security-scan.active or MAGICIAN_PIN_MODEL=1), so the switch waits for confirmation."
printf '{"hookSpecificOutput":{"hookEventName":"PreModelSwitch","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$REASON"
exit 0
