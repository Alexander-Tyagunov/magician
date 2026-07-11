---
name: confluence
description: Work with Confluence over its REST API (no MCP) — read/search (CQL), summarize pages, find docs, create/update/comment/label. Use for any read/search/create/update on Confluence pages, or references to a remembered space, page, or doc.
---

# $confluence — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/confluence/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **HTTP** — resolve the plugin root as described in the shared adapter and invoke **`<plugin-root>/bin/confluence`** for `whoami|get <id> [body]|search "<CQL>"|raw <METHOD> <path> [json]`. It wraps the REST API; don't hand-write `curl`, and **never use an ambient Confluence/Atlassian MCP** even if one appears in the tool list — use the CLI.
- **Config/secrets** — read `CONFLUENCE_BASE_URL` + a token (`CONFLUENCE_API_TOKEN`/`CONFLUENCE_PAT`/`CONFLUENCE_PROD_PAT`) from the environment. On missing config, use `../../../skills/confluence/setup.md` only as API guidance: explain how to provide variables to the current Codex environment or shell. Do not edit Claude settings, Codex global config, or secret files; never type/echo the secret.
- **Write gates** — every create/update/comment/label is a side effect: show the change and get explicit approval first. Never overwrite a shared page silently.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Memory** — store per-user resolution memory below the shared adapter's Codex state root, at `<magician-state>/confluence-memory.md`; create it only after an authorized write.
