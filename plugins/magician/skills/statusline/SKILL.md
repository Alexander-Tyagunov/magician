---
name: statusline
description: Explain Magician status-line availability in Codex. The shipped renderer is Claude Code-specific and this Codex adapter is intentionally a no-op.
---

# $statusline — Codex Adapter

Read `../../references/codex-adapter.md` for boundaries. Do **not** execute the source skill's configuration steps in Codex.

Codex does not currently provide the Claude Code `statusLine` input/configuration contract consumed by `magician-statusline`. Report status-line configuration as unsupported in Codex and make no changes. Never invoke `magician-ui`, never edit `~/.claude/settings.json`, and never record a preference on the user's behalf. If the user explicitly wants Claude Code configured, stop and ask them to run the Claude-side skill in Claude Code; this adapter must remain a no-op.
