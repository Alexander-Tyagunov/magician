# Autonomy — gather → plan → memorize → execute (don't make the owner babysit)

The plugin's whole promise: the human approves the **plan**, not a thousand file reads. If a run is
bombarding the user with "can I read this? and this? and git?", the run is broken — fix the posture,
don't push the cost onto the owner. Grounded in the autonomy-slider practice from Anthropic's
*Building effective agents* and the Claude Code docs: gate at **decisions**, not at every tool call.

## The loop

1. **Gather requirements.** Read the ask, the tickets, the target repos, the standards. Ask
   clarifying questions **up front, batched** (AskUserQuestion) — not drip-fed mid-execution.
2. **Plan.** Produce the plan/spec and show it **once** for approval (the gate). Scope, units,
   the repos touched, the guardrails, the rough agent/token cost.
3. **Memorize.** Before executing, write the plan + requirements + decisions + **kg `file:line`
   pointers** + the discovered standards to `.workspace/shared/` and `.workspace/local/session-state.md`
   so every stage/subagent reads them by path and nothing is re-derived (see
   [subagent-context.md](subagent-context.md), [code-standards.md](code-standards.md)).
4. **Execute autonomously.** Run the whole plan without stopping to ask permission for each read,
   grep, or git status. Re-gate **only** on the defined side effects.

## The mechanism: Claude Code **auto mode** (a skill can't switch modes — magician configures it)

Steps 1–4 are a *posture*, not enforcement. What actually stops the prompts is Claude Code's
**auto mode**: a classifier reviews each action, auto-approves reads + request-aligned work, and **gates**
writes, deploys, force-push, mass-deletion, and other escalations — honoring boundaries you state in chat
("don't push until I review"). That is exactly "reads proceed, writes gate."

A plugin **cannot** switch the permission mode of a running session — mode is user-set (Shift+Tab),
`--permission-mode`, or `defaultMode` in settings. So magician *configures* auto mode and you **restart** into it:

- `magician-ui automode` sets `permissions.defaultMode: "auto"` **and** (required on Vertex/Bedrock/Foundry)
  `env.CLAUDE_CODE_ENABLE_AUTO_MODE=1` in `~/.claude/settings.json`. Restart → sessions start in auto mode.
- Requires a supported model (Opus 4.7+/Sonnet 5) and, on Team/Enterprise, org-owner enablement. If the
  status bar still shows **Manual** after restart, auto mode isn't available for the account → `automode --off`.
- `acceptEdits` mode only auto-approves file edits + `mkdir/mv/cp/sed`; **every other Bash, MCP, and skill
  call still prompts.** A run stuck in acceptEdits *feels* un-autonomous because it is not auto mode.

## Don't make reads a gate (the acceptEdits fallback)

When auto mode isn't on, reading/searching/read-only git still must not prompt. Magician auto-approves a
read-only surface (Read/Grep/Glob/LS + read-only git + `kg`/`ctx` + **jira/confluence READS** + test/lint/build
runners + `gh` reads) via `magician-ui allow` (applied on install/upgrade, opt-out `magician-ui allow --off`).
Jira/Confluence **writes** are deliberately *not* allowed — they gate. In auto mode the classifier supersedes
this list (and drops broad interpreter/package-manager allow rules by design), so auto mode is strictly better;
the allow-list is the floor for acceptEdits/Manual sessions.

**Jira/Confluence: use the bundled MCP-free CLIs, never an ambient MCP.** Magician ships `jira` and
`confluence` HTTP CLIs on PATH — already allowed, with a shared throttle/cache and bulk ops, so they
don't prompt per call. If a run (or a hand-rolled `Workflow`) reaches for an ambient
`mcp__…jira…`/`…confluence…` tool instead, magician nudges it back to the CLI: that MCP prompts on
*every* call and bypasses the plugin's pacing — exactly what bombards the owner with approvals. Tell
subagents to use `jira`/`confluence` too (on PATH for them).

**Retrieve, don't grind.** Ground via the **knowledge graph** (`kg query`/`blast`/`neighbors`) instead
of broad `grep` and whole-file reads — targeted `file:line`, far fewer tokens, shared across agents,
and it uses the *allowed* Grep/kg tools rather than raw `Bash` searches that each prompt. For work
spanning **multiple repos**, index each (`cd <repo> && kg init`) at plan time and query per-repo — kg
is keyed on the cwd repo root, so cross-repo greps are the wrong tool. See
[knowledge-graph/references/retrieval.md](../skills/knowledge-graph/references/retrieval.md).

## What still gates (never auto-approve)

Writes/`Edit`, `git commit`/`add`/`push`, PR create/merge, ticket create/comment, `rm`/destructive
ops, credential entry, anything outward-facing. These are the decisions worth the owner's attention;
everything read-only is not. Dial autonomy **up** where verification is cheap and rollback is real,
**down** where it isn't — but never down to "approve every file read."
