---
name: orchestrate
description: Drives full multi-agent implementation from a blueprint — fans out parallel-safe tasks into waves, runs sequential tasks in order, resolves conflicts, then verifies. Use to execute an approved plan.
---

# $orchestrate — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/orchestrate/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Translate source agent teams and `magician:*` profiles into available generic Codex agents with self-contained prompts. Dispatch only independent blueprint nodes in parallel, collect results through normal agent completion/waiting, and run sequential nodes locally or in order. Do not invent agent-closing or native workflow APIs. Commits are optional side effects: stage only task-owned files and require the user's commit authorization.
