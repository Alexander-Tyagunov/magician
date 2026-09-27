---
name: jira
description: Work with Jira over its REST API (no MCP) — read/search (JQL), look up tickets, my board/sprint, create/comment/@mention/transition/link/worklog, MR investigation, clone the ticket's repo. Use for any read/search/create/update/transition on Jira issues, or references to a remembered board, project, epic, or person.
---

# $jira — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/jira/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and rules.

Codex equivalents:
- **HTTP** — resolve the plugin root as described in the shared adapter and invoke **`<plugin-root>/bin/jira`** for `myself|mine [--max N]|sprint <boardId> [--max N]|get <KEY>|comments <KEY>|search "<JQL>" [--max N]|transitions <KEY>|board <name>|url <KEY>|create '<fields-json>'|link <inward> "<Type>" <outward>|raw <METHOD> <path> [json]`. It is throttle-aware/cached/self-pacing. Use this CLI by default; use another installed Jira integration only when the user explicitly says they prefer it. Never use a bare PATH command, a versioned cache path, hand-written HTTP, or module import. For bulk work call the absolute CLI once per operation; stop on persistent 429 and increase pacing.
- **Config/secrets** — the CLI reads `JIRA_BASE_URL` + a token (`JIRA_API_TOKEN`/`JIRA_PAT`/`JIRA_PROD_PAT`) and, for Cloud, `JIRA_EMAIL` from the environment Codex runs in. Ignore source instructions about plugin options/userConfig; in Codex, credentials come only from the environment variables above. On missing config, use `../../../skills/jira/setup.md` only as API guidance: explain how to export the variables in the user's shell profile or the shell that launches Codex (a hardened `shell_environment_policy` can strip these variables), then restart Codex from that shell — a running Codex does not see variables exported later. The base URL must use https (localhost is exempt) and be the final URL, because redirects are not followed. Do not edit Claude settings, Codex global config, or secret files; never type/echo the secret, and never print or inspect the environment (`env`, `printenv`, `echo $…`) — the CLI reads it itself.
- **Write gates** — every create/comment/transition/link/worklog is a side effect: show the payload and get explicit approval first.
- **Questions** — use Codex's question/approval UI where the source says AskUserQuestion.
- **Research** — when authoring a ticket needs grounding, invoke `$magic` first.
- **Memory** — store per-user resolution memory below the shared adapter's Codex state root, at `<magician-state>/jira-memory.md`; create it only after an authorized write.
