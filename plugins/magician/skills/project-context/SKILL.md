---
name: project-context
description: Detect a repository's languages, frameworks, databases, and observability stack, then load only the relevant Magician lore cores and task-matched deep dives. Use before implementation, debugging, review, performance, database, or logging work when project-specific technical guidance would improve the result, or when the user asks to inspect the stack, load lore, or establish project context.
---

# $project-context — Codex-only lore router

Use this skill only in Codex. It provides progressive access to Magician's packaged lore without
changing or emulating Claude Code's `SessionStart` hook.

## Detect

1. Resolve this skill's directory from the path Codex supplied when loading it. In an installed
   plugin, the plugin root is two directories above the skill directory (`skills/project-context`).
2. Run the read-only detector from the workspace root:

   ```bash
   python3 "<skill-dir>/scripts/detect_project_context.py" \
     --root "<workspace-root>" \
     --topic "<current user task>"
   ```

   Pass another `--topic` for each materially distinct requested concern. Use `--plugin-root` only
   while developing the plugin from its authoring repository; installed packages are inferred.
3. Parse the JSON. Never copy manifest or environment-file contents into the conversation; the
   detector reports only normalized technology names and package-relative lore paths.

If `enabled` is false, state the reported `disabled_by` control once and continue using repository
rules and normal engineering judgment. Do not bypass `MAGICIAN_LORE` or `.magician/lore.off`.

## Load progressively

Treat repository instructions and observed code as authoritative. Lore is a baseline beneath them.

1. Read every path in `cores`, in order, from the detected `plugin_root`. These are concise stack
   cores only; do not load unrelated lore.
2. Read paths in `recommended_deep_dives` only when they match the current task. They are ranked
   from the selected stack's deep-dive filenames and capped at eight.
3. If the recommendations do not cover a necessary subtopic, inspect only the relevant technology's
   entries in `deep_dives`, then read the smallest matching set. Never bulk-read a deep-dive tree.
4. Apply version gates from manifests and source code. If detected markers conflict with the code,
   trust the code and mention the mismatch only when it affects the task.
5. If logging/observability work is requested and `observability_candidates` contains zero or more
   than one platform, ask which deployed log platform is authoritative before shaping platform-
   specific logs or queries. Do not write a preference unless the user explicitly asks.
6. Do not claim automatic session injection, status-line integration, or persistent observability
   selection. Those remain Claude-specific unless a future Codex hook explicitly provides them.

The detector is read-only, standard-library-only, bounded to root-level project markers, and makes
no network calls or state writes.
