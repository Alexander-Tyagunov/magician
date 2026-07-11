---
name: inscribe
description: Creates a new reusable skill — can be suggested by the pattern detector after repeated requests. Use to scaffold a new SKILL.md.
---

# $inscribe — Codex Adapter

Read `../../references/codex-adapter.md`, then use the installed **`$skill-creator`** workflow for Codex skill authoring. Treat `../../source-skills/inscribe/SKILL.md` as intent/gating guidance only; do not create or modify the Claude source `skills/` tree.

Create project-scoped Codex skills under `.agents/skills/<name>/SKILL.md` (or the location explicitly selected by the user), validate them according to `$skill-creator`, and explain that discovery may require starting a new task. Preserve the source gates for name, trigger description, scope, examples, and user approval. Do not commit unless the user explicitly authorizes a commit after reviewing the generated files.
