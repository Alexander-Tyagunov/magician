---
name: jira
description: Work with Jira over its REST API (no MCP) — read/search (JQL), look up tickets, my board/sprint, create/comment/@mention/transition/link/worklog, MR investigation, clone the ticket's repo. Use for any read/search/create/update/transition on Jira issues, or references to a remembered board, project, epic, or person.
---

# /jira — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/jira/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **HTTP** — use Codex's shell (`curl`) for all REST calls; no MCP.
- **Config/secrets** — read `JIRA_BASE_URL` + a token (`JIRA_API_TOKEN`/`JIRA_PAT`/`JIRA_PROD_PAT`) from the environment. On missing config run the source `setup.md`: guide the user to save a token to their settings; never type/echo the secret.
- **Write gates** — every create/comment/transition/link/worklog is a side effect: show the payload and get explicit approval first.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Research** — when authoring a ticket needs grounding, invoke the Codex `/magic` adapter first.
- **Memory** — read/write per-user resolution memory at `${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}/jira-memory.md`.
