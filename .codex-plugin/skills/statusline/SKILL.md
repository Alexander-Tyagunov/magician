---
name: statusline
description: Enable, configure, or disable the Magician CLI status line ("Magician Claude CLI UI") — a lightweight always-on bar showing live context %, a context-rot warning, a token-flow sparkline, model · git · cost, and the active skill/workflow/loop. Use when the user wants to turn on/off or configure the status bar, or see live context/tokens in the console.
---

# /statusline — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/statusline/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **CLI** — use the bundled **`magician-ui` CLI** (on PATH when the plugin is enabled): `magician-ui status | enable [--all|--only a,b] | set <a,b,c> | disable`. It installs a version-independent renderer and edits `~/.claude/settings.json` **safely** (timestamped backup → JSON-validate → atomic write; only the `statusLine` key). One command per call keeps approvals to a single allow for `magician-ui`.
- **Components** — `context` (bar+%+tokens), `rot` (⚠/🔴), `spark` (token-flow sparkline), `meta` (model·git·cost), `skill` (active skill/workflow/loop). Let the user pick a subset; default all.
- **Config surface** — the status line itself is Claude-Code-specific; on Codex, `magician-ui` still records the user's preference and manages the config, and the renderer (`magician-statusline`) reads Claude Code's `context_window` JSON on stdin. It consumes no tokens and can't break the host: any error prints an empty line and exits 0.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion (to pick components).
- **Safety** — never hand-edit `settings.json`; always go through `magician-ui`.
