---
name: knowledge-graph
description: Local code knowledge-graph + cache (no MCP, no network) — index a repo and retrieve ranked file:line for a topic instead of grepping whole files; show graph/cache status; blast-radius / dependents of a file; refresh or reset. Use for "knowledge graph status", "index this repo", "what depends on <file>", "find the code for <thing>".
---

# /knowledge-graph — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/knowledge-graph/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **Engine** — use the bundled **`kg` CLI** (on PATH when the plugin is enabled): `kg check | init [--max N|--all] | refresh | status [--json] | query "<text>" [--k N] | neighbors <sym|file> | blast <file|sym> | stale | cache stats|clear | daemon start|stop|status | reset`. Pure stdlib by default; one command per call keeps Codex approvals to a single allow for `kg`. Don't hand-write graph logic.
- **Storage** — global, per-repo under `~/.claude/magician/knowledge-graph/` (override `MAGICIAN_HOME`); a durable on-disk artifact every agent can read, so there's no context loss across hand-offs.
- **Build/reset gates** — `kg init` (first build on a large repo) and `kg reset` (destroys index+cache) are side effects: state the repo (and rough file count for a build), get explicit approval first. Reads need none.
- **Opt-out** — respect `knowledge-graph: "disabled"` in `${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}/integration-prefs.json` for proactive suggestions; a direct request clears it.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Visualize** — only when asked; `kg status --json` then render via the available visualization tool. Plain-text `kg status` is the default.
- **Integration** — the Codex `/magic` adapter uses `kg query` as an internal codebase source; the `/divine` adapter uses `kg blast` for change blast-radius.
