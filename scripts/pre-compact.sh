#!/usr/bin/env bash
# PreCompact hook (matcher "auto|manual"): just before Claude Code summarizes the session, asks for
# the running state to be written to .workspace/local/session-state.md, the file the post-compaction
# hook (compact-context.sh) restates. It reads only the trigger field of the event, never the
# transcript, writes nothing and never blocks a compaction. Plain bash 3.2; always exits 0.
export LC_ALL=C

INPUT=""; [ ! -t 0 ] && INPUT=$(head -c65536 2>/dev/null | tr -d '\n\r')

TRIGGER=""
re_trig='"trigger"[[:space:]]*:[[:space:]]*"(auto|manual)"'
[[ $INPUT =~ $re_trig ]] && TRIGGER=${BASH_REMATCH[1]}

STATE=".workspace/local/session-state.md"
HAVE="none is written yet"
[ -f "$STATE" ] && HAVE="one exists and gets the latest state"

case "$TRIGGER" in
  auto)   WHEN="The context is full, so Claude Code is about to summarize this session" ;;
  manual) WHEN="A /compact was requested, so Claude Code is about to summarize this session" ;;
  *)      WHEN="Claude Code is about to summarize this session" ;;
esac
NOTE="${WHEN}. The running state (goal, done and remaining items, decisions, blockers, artifact paths, the next step) belongs in ${STATE} before the summary is made; ${HAVE}. The post-compaction hook restates the head of that file, so what is written there survives the summary."

printf '{"systemMessage":"magician: state goes to %s before the compaction summary.","hookSpecificOutput":{"hookEventName":"PreCompact","additionalContext":"%s"}}\n' "$STATE" "$NOTE"
exit 0
