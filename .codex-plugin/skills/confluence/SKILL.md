---
name: confluence
description: Work with Confluence over its REST API (no MCP) — read/search (CQL), summarize pages, find docs, create/update/comment/label. Use for any read/search/create/update on Confluence pages, or references to a remembered space, page, or doc.
---

# $confluence — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/confluence/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **HTTP** — resolve the plugin root as described in the shared adapter and invoke **`<plugin-root>/bin/confluence`** for `whoami|get <id> [body|storage]|search "<CQL>" [--max N]|children <id> [--max N]|comments <id>|raw <METHOD> <path> [json]`. It wraps the REST API; don't hand-write `curl`. Use this CLI by default; use another installed Confluence integration only when the user explicitly says they prefer it.
- **Config/secrets** — the CLI reads `CONFLUENCE_BASE_URL` + a token (`CONFLUENCE_API_TOKEN`/`CONFLUENCE_PAT`/`CONFLUENCE_PROD_PAT`) and, for Cloud, `CONFLUENCE_EMAIL` from the environment Codex runs in; on an Atlassian Cloud site shared with Jira it can reuse the Jira token and email. Ignore source instructions about plugin options/userConfig; in Codex, credentials come only from the environment variables above. On missing config, use `../../../skills/confluence/setup.md` only as API guidance: explain how to export the variables in the user's shell profile or the shell that launches Codex (a hardened `shell_environment_policy` can strip these variables), then restart Codex from that shell — a running Codex does not see variables exported later. The base URL must use https (localhost is exempt) and be the final URL, because redirects are not followed. Do not edit Claude settings, Codex global config, or secret files; never type/echo the secret, and never print or inspect the environment (`env`, `printenv`, `echo $…`) — the CLI reads it itself.
- **Write gates** — every create/update/comment/label is a side effect: show the change and get explicit approval first. Never overwrite a shared page silently.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Memory** — store per-user resolution memory below the shared adapter's Codex state root, at `<magician-state>/confluence-memory.md`; create it only after an authorized write.
