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

## The mechanism: Claude Code **auto mode** (the user's choice — a plugin can't switch modes)

Steps 1–4 are a *posture*, not enforcement. What actually stops the prompts is Claude Code's
**auto mode**: a classifier reviews each action, auto-approves reads + request-aligned work, and **gates**
writes, deploys, force-push, mass-deletion, and other escalations — honoring boundaries you state in chat
("don't push until I review"). That is exactly "reads proceed, writes gate."

Since **2026-08-14** auto mode is the default permission mode for new Pro/Max/Team sessions. A plugin
**cannot** change the permission mode, and magician writes no permission settings (no allow rules, no
`defaultMode`). The user picks the mode:

- **Shift+Tab** cycles the mode of the running session; `claude --permission-mode auto` starts a session in it.
- **`/config`** sets the default mode for new sessions. Claude Code honors a default of `auto` only from the
  user's own settings, never from a repository's `.claude/settings.json` or `.claude/settings.local.json`, so
  a repository can't grant itself auto mode.
- When auto mode isn't offered, the model in use doesn't support it or it is turned off in settings
  (`permissions.disableAutoMode`); the Claude Code permissions docs list supported models.
- The classifier also reviews every message Claude sends another session with `SendMessage` before it is
  delivered — see [cross-session.md](cross-session.md).
- `acceptEdits` mode only auto-approves file edits + `mkdir/mv/cp/sed`; **every other Bash, MCP, and skill
  call still prompts.** A run stuck in acceptEdits *feels* un-autonomous because it is not auto mode.

## Reads outside auto mode (the user's own allow rules)

A skill's `allowed-tools` pre-approves only the narrow commands it lists, for that skill's turn; every other
action goes through the normal permission prompt unless the session runs in auto mode. In acceptEdits or
default mode, each read-only command that no allow rule covers prompts. Answering a prompt
with **"Yes, and don't ask again"**, or adding rules with **`/permissions`**, records an allow rule the user
owns and controls. Magician versions up to 4.14 added a read-only allow list (and possibly
`defaultMode: "auto"`) to the user settings; `magician-ui cleanup` removes those entries only where magician's
`cli-ui.json` records adding them, and keeps matching rules it has no record of.

**Retrieve, don't grind.** When a repository has a **knowledge-graph** index, `kg query`/`blast`/`neighbors`
return targeted `file:line` results — far fewer tokens than broad searches and whole-file reads, and shared
across agents. For work spanning **multiple repos**, each repo has its own index (`cd <repo> && kg init`) and
is queried from its own root, because kg is keyed on the cwd repo root. See
[knowledge-graph/references/retrieval.md](../skills/knowledge-graph/references/retrieval.md).

## What still gates (never auto-approve)

Writes/`Edit`, `git commit`/`add`/`push`, PR create/merge, ticket create/comment, `rm`/destructive
ops, credential entry, anything outward-facing. These are the decisions worth the owner's attention;
everything read-only is not. Dial autonomy **up** where verification is cheap and rollback is real,
**down** where it isn't — but never down to "approve every file read."
