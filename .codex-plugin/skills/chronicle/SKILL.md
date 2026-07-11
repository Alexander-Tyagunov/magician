---
name: chronicle
description: Memory & context steward — session-learning history, the global reference store (repos/projects/ideas), AND live context management (size status, post-compaction resume capsule, project learnings, promotion). Use to review past sessions, remember/recall/forget a reference, check context size, resume after compaction, or capture/consolidate learnings.
---

# $chronicle — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/chronicle/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Context management is **manual in Codex** unless the installed Codex hook manifest explicitly includes an equivalent lifecycle event. Invoke the absolute `<plugin-root>/bin/ctx` path for `pct --transcript <p>`, `resume --keep`, `learn --add "<fact>" [--global]`, and `consolidate`. Do not claim `UserPromptSubmit`, `PreCompact`, `Stop`, or `SessionStart` automation: those are Claude-side hooks. A Codex task cannot read a live token count or force/steer compaction; capture or restore a capsule only when requested or when the current host exposes the needed transcript/context input. Details in `../../../skills/chronicle/references/context-mgmt.md`.
