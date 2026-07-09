#!/usr/bin/env bash
# PreToolUse(mcp__*jira* / *confluence* / *atlassian*) — magician ships MCP-FREE `jira` and
# `confluence` HTTP CLIs (on PATH, auto-approved by `magician-ui allow`, with a shared
# throttle/cache and bulk ops). When a session reaches for an *ambient* Atlassian MCP instead
# — which prompts on every call, has no shared pacing, and bypasses the plugin's hygiene — steer
# it back to the bundled CLI. This is the failure mode where a run hand-rolls Workflow scripts that
# grab the ambient `mcp__…jira…` tools instead of invoking /jira, and the owner gets prompt-bombed.
#
# Non-blocking (additionalContext only). Throttled per session. Opt-out aware (integration-prefs
# `jira`/`confluence` = "disabled"). Silent if the bundled CLI for that service isn't present.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
PREFS="$PLUGIN_DATA/integration-prefs.json"
INPUT=$(cat 2>/dev/null || printf '{}')

DECIDE=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('none default'); raise SystemExit
tn = (d.get('tool_name', '') or '').lower(); sid = d.get('session_id') or 'default'
svc = 'none'
if tn.startswith('mcp__'):
    if 'confluence' in tn:
        svc = 'confluence'
    elif 'jira' in tn or 'atlassian' in tn:
        svc = 'jira'
print(svc, sid)
" 2>/dev/null || echo "none default")
SVC=${DECIDE%% *}; SID=${DECIDE##* }
[ "$SVC" = "none" ] && exit 0

# Opt-out for this service (user told us they don't use magician's jira/confluence).
state=$(python3 -c "import json;print(json.load(open('$PREFS')).get('$SVC','ask'))" 2>/dev/null || echo ask)
[ "$state" = "disabled" ] && exit 0

# Only steer if the bundled CLI actually exists (else the MCP is the user's only path — stay silent).
CLI="${CLAUDE_PLUGIN_ROOT:-}/bin/$SVC"
[ -x "$CLI" ] || command -v "$SVC" >/dev/null 2>&1 || exit 0

# Throttle: at most twice per session per service — inform, don't nag.
MARK="$PLUGIN_DATA/ctx/${SID}.${SVC}mcpnudge"
N=$(cat "$MARK" 2>/dev/null || echo 0)
[ "$N" -ge 2 ] 2>/dev/null && exit 0
mkdir -p "$(dirname "$MARK")"; echo "$((N+1))" > "$MARK"

MSG="Magician ships an MCP-free \`$SVC\` CLI on PATH (auto-approved by \`magician-ui allow\`, with shared throttle + cache + bulk ops). Prefer \`$SVC <cmd>\` over this ambient MCP: the MCP prompts on every call, has no shared pacing, and bypasses the plugin's hygiene — which is what bombards the owner with approvals in a hand-rolled workflow. Use the /magician:$SVC skill or \`$SVC --help\` for the command surface. (If you don't use magician's $SVC, ignore — it stays quiet after this.)"

python3 -c "import json,sys;print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','additionalContext':'[MAGICIAN] '+sys.argv[1]}}))" "$MSG"
exit 0
