---
name: portal
description: Creates a git worktree for isolated feature work (and documents cleanup post-merge); respects the disableGit preference. Use to isolate a feature on its own branch/worktree.
---

# $portal — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/portal/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Codex has no Magician `WorktreeCreate` hook in the shipped hook manifest. After creating a worktree, explicitly copy or summarize only the required task context into the dispatch prompt (Goal, Scope, approved plan/spec paths, constraints, verification, Return format), and point agents at repository `AGENTS.md` files. Do not copy Claude session state or claim automatic context propagation. Use a `codex/` branch prefix unless the user requests another name, and report the absolute worktree path and cleanup command without running cleanup.
