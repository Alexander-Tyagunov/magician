---
name: almanac
description: One-time Codex workspace setup — creates .workspace/ structure, .gitignore entries, a lean AGENTS.md, and suggests relevant Codex capabilities. Run once per project.
---

# $almanac — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/almanac/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Create or update `AGENTS.md`, never `CLAUDE.md`, and skip Claude permission/MCP settings. Do not alter `.claude/`, `.claude-plugin/`, or Claude configuration. Recommend Codex plugins/MCPs only when relevant and installed/available; do not claim setup succeeded without evidence. Record the step-1 workspace mode in `<magician-state>/workspace-strategy.json` (the shared adapter's Codex state root), not the source's Claude plugin data folder.
