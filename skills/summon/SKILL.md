---
name: summon
description: Spawns parallel subagents for independent tasks — seeds each with the full skill registry
keep-coding-instructions: true
---

# /summon — Parallel Subagent Spawner

Dispatch multiple subagents to work on independent tasks simultaneously.

## When to Use

Only for tasks that are explicitly PARALLEL-safe (from /blueprint parallelism map). Never summon agents for sequential tasks — they will conflict.

## Skill Registry (inject into every subagent)

Every summoned agent receives this skill list so it knows its toolbox:

Available skills: /conjure (design), /blueprint (planning), /forge (task execution),
/ward (TDD), /unravel (debugging), /certify (verification), /summon (spawn agents),
/orchestrate (multi-agent run), /scrutinize (code review), /absorb (integrate review),
/portal (git worktree), /seal (ship PR), /manifest (full SDLC), /almanac (workspace init),
/chronicle (session history), /magic (research & consulting), /sentinel (security scan),
/accelerate (performance), /deploy (CI/CD), /inscribe (write skills), /autopsy (post-mortem)

## Process

1. **Identify parallel-safe tasks** from the blueprint parallelism map
2. **For each parallel task**, construct a precise agent prompt containing:
   - The task description (full text from the plan)
   - Relevant file paths and context
   - The skill registry above
   - Expected output format: `STATUS: DONE | BLOCKED | NEEDS_CONTEXT` + summary
3. **Dispatch all agents simultaneously** (not sequentially)
4. **Collect results** — wait for all agents to complete
5. **Handle failures** — BLOCKED agents: assess blocker, re-dispatch with more context
6. **Report summary** — what each agent completed

## Agent Prompt Template

You are implementing task: <task name>

Context: <relevant background>

Task:
<full task text from plan>

Available magician skills: <skill registry>

When done: output STATUS: DONE followed by a one-paragraph summary of what was implemented and committed.

## Completion Signal

"Summon complete. All N agents finished. Run /certify or proceed to next sequential task."
