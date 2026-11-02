#!/usr/bin/env bash
# StopFailure hook (matcher "max_output_tokens"): when a turn ends because the model hit its output
# limit, shows the user one systemMessage pointing at /compact and the session-state file. The
# event's text is not read: the matcher already names the failure. Writes nothing. Plain bash
# 3.2; always exits 0.
export LC_ALL=C

[ ! -t 0 ] && head -c65536 >/dev/null 2>&1   # drain stdin; nothing in the event is used

STATE=".workspace/local/session-state.md"
if [ -f "$STATE" ]; then
  HAVE="$STATE holds the running state, so a smaller next step can start from it"
else
  HAVE="a running state written to $STATE survives a compaction"
fi
printf '{"systemMessage":"magician: the turn stopped at the output token limit. /compact frees context for a shorter next step, and %s."}\n' "$HAVE"
exit 0
