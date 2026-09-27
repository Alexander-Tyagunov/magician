---
name: statusline
description: Explain Magician status-line availability in Codex. Claude Code's status-line renderer is not shipped in the Codex package; this adapter is intentionally a no-op.
---

# $statusline — Codex Adapter

Read `../../references/codex-adapter.md` for boundaries. Do **not** execute the source skill's configuration steps in Codex.

Codex does not currently provide the Claude Code `statusLine` input/configuration contract consumed by `magician-statusline`, so neither `magician-statusline` nor `magician-ui` is shipped in the Codex package. Report status-line configuration as unsupported in Codex and make no changes. Never invoke `magician-ui`, never edit `~/.claude/settings.json`, and never record a preference on the user's behalf. If the user explicitly wants Claude Code configured, stop and ask them to run the Claude-side skill in Claude Code; this adapter must remain a no-op.
