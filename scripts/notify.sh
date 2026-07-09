#!/usr/bin/env bash
# Notification hook — surfaces long-run agent lifecycle pings (Claude Code `Notification` event,
# 2.1.198: agent_completed / agent_needs_input). So a long /weave, /orchestrate, /loop, or /goal
# run tells you when it finishes or needs you, instead of you watching it.
#
# SAFETY: fully fail-safe — any error exits 0, never blocks the session. Non-spammy — it ignores
# permission/idle notifications and only reacts to agent lifecycle ones.
# CONFIG (env): MAGICIAN_NOTIFY=desktop → OS notification (macOS/Linux) + bell;
#               MAGICIAN_NOTIFY=off → silent; unset (default) → one concise stderr line.
set -uo pipefail

INPUT=$(cat 2>/dev/null || true)

# Only react to agent lifecycle notifications; stay silent for everything else.
case "$INPUT" in
  *agent_completed*|*agent_needs_input*) : ;;
  *) exit 0 ;;
esac
[ "${MAGICIAN_NOTIFY:-}" = "off" ] && exit 0

KIND="agent update"
case "$INPUT" in
  *agent_needs_input*) KIND="needs your input" ;;
  *agent_completed*)   KIND="run complete" ;;
esac

MSG=$(printf '%s' "$INPUT" | python3 -c '
import json,sys
try: d=json.loads(sys.stdin.read())
except Exception: print(""); sys.exit()
m=d.get("message") or d.get("notification") or d.get("body") or ""
if isinstance(m,dict): m=m.get("message") or m.get("text") or ""
print(str(m)[:160])
' 2>/dev/null || true)

case "${MAGICIAN_NOTIFY:-}" in
  desktop|1|on|true|yes)
    if command -v osascript >/dev/null 2>&1; then
      osascript -e "display notification \"${MSG:-$KIND}\" with title \"✦ Magician\" subtitle \"${KIND}\"" >/dev/null 2>&1 || true
    elif command -v notify-send >/dev/null 2>&1; then
      notify-send "✦ Magician — ${KIND}" "${MSG:-}" >/dev/null 2>&1 || true
    fi
    printf '\a' >&2 2>/dev/null || true
    ;;
  *)
    printf '✦ magician — %s%s\n' "$KIND" "${MSG:+: $MSG}" >&2 2>/dev/null || true
    ;;
esac
exit 0
