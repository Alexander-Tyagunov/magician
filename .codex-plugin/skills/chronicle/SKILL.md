---
name: chronicle
description: Memory & context steward — session-learning history, the global reference store (repos/projects/ideas), AND live context management (size status, post-compaction resume capsule, project learnings, promotion). Use to review past sessions, remember/recall/forget a reference, check context size, resume after compaction, or capture/consolidate learnings.
---

# /chronicle — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/chronicle/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Context management uses the bundled **`ctx` CLI** (on PATH when enabled): `ctx pct --transcript <p>` (size %), `ctx resume --keep` (print capsule), `ctx learn --add "<fact>" [--global]`, `ctx consolidate`. The hooks (UserPromptSubmit/PreCompact/Stop/SessionStart) drive tracking + capsule capture automatically. Honest limits: a plugin can't read a live token count or force/steer compaction — it warns early and preserves a lossless capsule. Details in `../../../skills/chronicle/references/context-mgmt.md`.
