---
name: orchestrate
description: Drives full multi-agent implementation from a blueprint — fans out parallel-safe tasks into waves, runs sequential tasks in order, resolves conflicts, then verifies. Use to execute an approved plan.
allowed-tools: Bash(git status:*), Bash(git log:*), Task
argument-hint: [plan-file]
---

# /orchestrate — Multi-Agent Implementation

Execute an entire blueprint with parallel + sequential agent dispatch. (This skill absorbed the former `/summon` — wave coordination and parallel spawning are one skill.)

## Pick the right engine first

- **This skill** — the default: you control waves explicitly from a blueprint, with conflict checks between them.
- **[`/weave`](../weave/SKILL.md)** — for *adaptive multi-item delivery* (N tickets/features, a migration, a batch sweep) where you compose the pipeline to the work: it builds ONE native Workflow with magician's guardrails (TDD per unit, kg grounding, certify, multi-lens review + adversarial verify, write gates). Prefer it over hand-rolling many agents.
- **Native dynamic workflows** — for very large plans (hundreds of independent units: migrations, sweeping refactors), mention "workflow" so Claude builds a dynamic orchestration plan that fans across many subagents with self-verification. Works best in **auto mode**. Nested subagents (agents spawning agents, capped depth) help manage context on deep work.
- **Agent teams** — when independent workers need to talk to each other and share a task list (research/review, cross-layer features), prefer an agent team over one-way subagents.

Choose by scale and whether workers must communicate; otherwise proceed with waves below. **Whichever engine you pick, the context contract (below) applies to every spawned agent** — no worker inherits this conversation.

## Effort & model

Scale `/effort` to plan size (high/xhigh for large plans). For dispatched implementation agents, pick the coding-optimal tier and suggest upgrading the session model if it's older than the latest. See [lore/models.md](../../lore/models.md).

## Process

1. **Read the blueprint** — most recent in `.workspace/shared/plans/` unless `$ARGUMENTS` names one. If ambiguous, ask which plan; **end your turn and wait**.
2. **Build the execution graph** — group PARALLEL-annotated tasks into waves; SEQUENTIAL tasks are singletons that run in order.
3. **Execute wave by wave.** For each parallel wave, dispatch all its tasks in ONE message (multiple `Task` calls) so they run concurrently. Wait for the whole wave before the next. Run sequential tasks one at a time.
4. **After each wave** — sanity check: `git status`, `git log --oneline -3`. Refresh the shared session capsule so the next wave's agents pick up current state with no context loss: write goal · completed/remaining tasks · decisions · blockers · artifact paths to `.workspace/local/session-state.md` (the spawn template tells every agent to read it first).
5. **After all waves** — run /certify.
6. **Report** — completed tasks and any blockers.

## Agent prompt — context contract (no context loss)

Spawned agents see NONE of this conversation. Every `Task` prompt MUST be self-contained (see [lore/subagent-context.md](../../lore/subagent-context.md)):

```
Goal: implement task <N> — <one-line deliverable>.
Scope: files/paths in play: <exact list>. Out of scope: <...>.
Inputs: full task text from the plan (paste it), and the spec at .workspace/shared/specs/<feature>.md. FIRST read .workspace/local/session-state.md if it exists (current goal, decisions, blockers, artifact paths). Locate code with `kg query`/`kg blast`, not broad greps.
Constraints: follow TDD via /ward; conventions/lore: <...>; do not touch <deny paths>; definition of done: <...>.
Available magician skills: /conjure /blueprint /ward /unravel /certify /orchestrate /scrutinize /portal /seal /manifest /almanac /chronicle /magic /sentinel /accelerate /deploy /inscribe /autopsy
Return: STATUS: DONE | BLOCKED | NEEDS_CONTEXT, then a one-paragraph summary of what was implemented and committed.
```

## Handle results

- **DONE** — record it.
- **NEEDS_CONTEXT** — this is a context-completeness bug in the spawn prompt. Add the missing input and re-dispatch; don't guess for the agent.
- **BLOCKED** — assess the blocker, re-dispatch with more context, or escalate.

## Conflict detection

After each wave: `git status | grep -i conflict`. If conflicts are found, pause and resolve before continuing. (For parallel tasks that edit overlapping files, prefer worktree isolation per task.)

## Completion Signal

"Orchestrate complete. N tasks executed across M waves. Run /scrutinize for review."
