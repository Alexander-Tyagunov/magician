---
name: confluence
description: Work with Confluence over its REST API (no MCP) — read/search (CQL), summarize pages, find docs, create/update/comment/label. Use for any read/search/create/update on Confluence pages, or references to a remembered space, page, or doc.
---

# /confluence — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/confluence/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **HTTP** — use the bundled **`confluence` CLI** (on PATH when the plugin is enabled): `confluence whoami|get <id> [body]|search "<CQL>"|raw <METHOD> <path> [json]`. It wraps the REST API; don't hand-write `curl`.
- **Config/secrets** — read `CONFLUENCE_BASE_URL` + a token (`CONFLUENCE_API_TOKEN`/`CONFLUENCE_PAT`/`CONFLUENCE_PROD_PAT`) from the environment. On missing config run the source `setup.md`; never type/echo the secret.
- **Write gates** — every create/update/comment/label is a side effect: show the change and get explicit approval first. Never overwrite a shared page silently.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Memory** — read/write per-user resolution memory at `${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}/confluence-memory.md`.
