#!/usr/bin/env bash
# PreToolUse(Bash|PowerShell) — ABSOLUTE hard gate against catastrophic commands.
#
# Delegates to destructive_guard.py, which exits 2 on a match. An exit-2 PreToolUse hook stops the
# tool call BEFORE Claude Code evaluates permission rules, so this block overrides `allow` rules and
# fires in every permission mode (default/acceptEdits/auto/bypass). No escape hatch by design.
#
# Honest scope (CWE-78): a denylist can't catch every obfuscation; this is a deterministic net for
# known catastrophic forms + common wrappers, layered under OS sandboxing + auto-mode's classifier +
# model judgment — not a complete sandbox. It only inspects the command; it never executes anything.
exec python3 "$(cd "$(dirname "$0")" && pwd)/destructive_guard.py"
