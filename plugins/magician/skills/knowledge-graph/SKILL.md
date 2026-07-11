---
name: knowledge-graph
description: Local code knowledge-graph + cache (no MCP, no network) — index a repo and retrieve ranked file:line for a topic instead of grepping whole files; show graph/cache status; blast-radius / dependents of a file; refresh or reset. Use for "knowledge graph status", "index this repo", "what depends on <file>", "find the code for <thing>".
---

# $knowledge-graph — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/knowledge-graph/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **Engine** — invoke the absolute **`<plugin-root>/bin/kg`** path: `check | init [--max N|--all] | refresh | status [--json] | query "<text>" [--k N] | neighbors <sym|file> | blast <file|sym> | stale | cache stats|clear | daemon start|stop|status | reset`. Pure stdlib by default; don't hand-write graph logic.
- **Storage** — set `MAGICIAN_HOME` to the shared adapter's Codex state root before invoking `kg`; never default Codex runs to `~/.claude`. The graph remains global and per-repo under that root.
- **Build/reset gates** — `kg init` (first build on a large repo) and `kg reset` (destroys index+cache) are side effects: state the repo (and rough file count for a build), get explicit approval first. Reads need none.
- **Opt-out** — respect `knowledge-graph: "disabled"` in `<magician-state>/integration-prefs.json` for proactive suggestions; a direct request may update it only with write authorization.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Visualize** — only when asked; `kg status --json` then render via the available visualization tool. Plain-text `kg status` is the default.
- **Integration** — `$magic` uses `kg query` as an internal codebase source; `$divine` uses `kg blast` for change blast-radius.
