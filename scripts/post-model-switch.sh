#!/usr/bin/env bash
# PostModelSwitch hook: after the model changed, adds one line of context naming the old and new
# model, since effort tables and prompt-cache behaviour differ per model, and asks for a retest of the
# last clean task type before unattended runs trust the new model. Plain text on stdout is
# the documented context form for this event. Reads only from_model and to_model; writes nothing.
# Plain bash 3.2; always exits 0.
export LC_ALL=C

INPUT=""; [ ! -t 0 ] && INPUT=$(head -c65536 2>/dev/null | tr -d '\n\r')
[ -n "$INPUT" ] || exit 0
_field() {  # $1=key -> value when it is a plain model name, or nothing
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"([A-Za-z0-9._:/-]{1,80})\""
  if [[ $INPUT =~ $re ]]; then printf '%s' "${BASH_REMATCH[1]}"; fi
}
FROM=$(_field from_model)
TO=$(_field to_model)
[ -n "$TO" ] || exit 0
[ -n "$FROM" ] || FROM="the previous model"

printf 'magician: model changed from %s to %s; re-check effort and cache assumptions, since the effort table and the prompt cache (invalidated by a model switch) differ per model, and a security scan in progress now runs on the new tier; trust is per task type, so the last task type that ran clean is retested on the new model before unattended runs rely on it (lore/models.md).\n' "$FROM" "$TO"
exit 0
