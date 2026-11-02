---
name: orchestrate
description: Multi-agent implementation of a blueprint; parallel-safe tasks in waves, the rest in order, then verify. Use to execute an approved plan.
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), Task, AskUserQuestion, Bash(kg query *), Bash(kg blast *), Edit(./.workspace/local/session-state.md)
argument-hint: "[plan-file]"
---

# /orchestrate — Multi-Agent Implementation

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Execute an entire blueprint with parallel + sequential agent dispatch.

## Pick the right engine first

- **Inline with [`/ward`](../ward/SKILL.md)** — first check: when the plan's Files lists name 3 files or fewer in total (about 300 changed lines or fewer), run its tasks in order in the main loop, one `/ward` cycle each, with no `Task` call ([lore/fold-first.md](../../lore/fold-first.md)).
- **This skill** — the default above that size: you control waves explicitly from a blueprint, with conflict checks between them.
- **[`/weave`](../weave/SKILL.md)** — for *adaptive multi-item delivery* (N tickets/features, a migration, a batch sweep) where you compose the pipeline to the work: it builds ONE native Workflow with magician's guardrails (TDD per unit, kg grounding, certify, multi-lens review + adversarial verify, write gates). Prefer it over hand-rolling many agents.
- **Native dynamic workflows** — for very large plans (hundreds of independent units), mention "workflow" so Claude builds a dynamic orchestration plan across many subagents. Works best in **auto mode**.
- **Agent teams** — when workers must talk to each other and share a task list, prefer an agent team over one-way subagents.

Choose by scale and whether workers must communicate; otherwise proceed with waves below. **Whichever engine you pick, inline included, write `.workspace/local/session-state.md` (step 3) before the first task runs.** **The context contract (below) applies to every spawned agent** — no worker inherits this conversation.

## Effort & model

Effort: `medium` for implementation turns, `high` for certify/review/security turns (`xhigh` for very large plans; `max` only as an opt-in for frontier problems); on Bedrock/Vertex/gateways hold one level (an effort change drops the cache there). Dispatched implementers take the coding-optimal tier; suggest a session-model upgrade if it's older than the latest. See [lore/models.md](../../lore/models.md).

**Cap the fan-out.** The blueprint's parallelism map is the ceiling, not a floor. Above the inline threshold, a wave with two or more independent `Parallel: YES` tasks always fans out: one agent per task, dispatched together in one message, even when each task looks small. A one-task wave, or a sequential task you finish in a handful of tool calls, runs inline; that exception never applies to a parallel wave. Never spawn an agent purely to re-check work an agent just did — the per-task quality loop below is the check. See [lore/fold-first.md](../../lore/fold-first.md) and [lore/model-behavior.md](../../lore/model-behavior.md).

## Process

1. **Read the blueprint** — most recent in `.workspace/shared/plans/` unless `$ARGUMENTS` names one. If ambiguous, ask which plan via **AskUserQuestion** (one option per candidate plan file or folder, most-recent first); **end your turn at the call** and proceed with the chosen plan.
   - **Plan folder** (`plan.json` next to `plan.md`): `plan.json` is the source — read it with Read. Task N is `steps[N-1]`; a step with `review.status` of `deferred` is excluded from the graph (they are listed under `## Deferred — not executed this run` in `plan.md`). Check the last line of `plan.md`, `<!-- magician.plan/1 v<n> … -->`: if `v<n>` differs from `plan.json.version`, say the plan is stale and ask the user to re-run `plan-render all <dir>/plan.json` (or `/blueprint review <dir>`) before executing; do not run it from here.
   - **Plan folder with `plan.workflow.js`** (`plan-render workflow` writes it next to `plan.json`; deferred steps are already omitted): prefer running it as one native Workflow — read the file and pass its contents as the `Workflow` script, as `/weave` does. The Workflow tool is not pre-approved here, so Claude Code shows its approval prompt. Nothing is copied into `.claude/workflows/`. Confirm the file is the plan's own version first (its `meta.description` carries `v<n>`; a mismatch with `plan.json.version` means stale — re-render). Skip the workflow and fall back to waves (below) when `plan.workflow.js` is missing, when workflows are disabled (`disableWorkflows`, Pro without the `/config` toggle), when the user asks for wave-by-wave control, or when the Workflow run reports `nothing to resume` after an interruption. Each workflow `agent()` already carries the context contract and the return `schema` below; the per-task quality loop still runs on its results.
   - **Single `plan.md`** (legacy): parse it as before — `### Task N`, `Parallel:`, Files, the five TDD lines.
2. **Build the execution graph** — from `plan.json`, the `waves` are explicit: each wave's `parallel: true` steps run together, its `parallel: false` steps one at a time after them. From a legacy `plan.md`, group PARALLEL-annotated tasks into waves; SEQUENTIAL tasks are singletons that run in order. (With `plan.workflow.js` the graph is the script's `phase()`/`parallel()` structure — skip to step 5 when the run completes, after ticking the `- [ ]` boxes of every step its results report as done.)
3. **Execute wave by wave.** Before the first wave, write `.workspace/local/session-state.md` (goal · plan path · wave graph · decisions · blockers): with Task tools (TaskCreate/TodoWrite) absent on current models unless `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`, the plan file's `- [ ]` boxes plus that file are the compaction-proof checklist; tick a box only after its quality loop passes. When a parallel wave's prompts share a prefix (conventions, plan, return contract first; per-task text last), dispatch the **first task alone**, then the rest in ONE message (multiple `Task` calls) so siblings reuse the first agent's cached prefix; with no shared prefix, send the whole wave in one message. Wait for the whole wave before the next. Run sequential tasks one at a time. As each task's implementer returns, run the **Per-task quality loop** (below) before you mark that task done — completion is confirmed from the VCS diff, not the agent's report.
4. **After each wave** — sanity check: `git status`, `git log --oneline -3`. Rewrite `.workspace/local/session-state.md` (goal · completed/remaining tasks · decisions · blockers · artifact paths) so the next wave's agents start current and a mid-run compaction loses nothing (the spawn template tells every agent to read it first).
5. **After all waves** — run /certify. If it fails, fix and re-certify (bounded evaluator-optimizer loop) before reporting complete — never report done on a red certify.
6. **Report** — completed tasks and any blockers.

**Independent sessions aren't in the graph.** When a wave lands something that invalidates what a sibling Claude Code session is building on, and cross-session messaging is available, send that session one self-contained sentence. Feature-detect and skip silently; a wave never waits on a peer. See [lore/cross-session.md](../../lore/cross-session.md).

## Autonomy — approve the plan, then run

The blueprint is the gate. Once it's approved (step 1), run the rest — **Execute wave by wave**, the per-wave sanity checks, and the session-state refresh — **autonomously**: don't stop to ask the owner before reading, searching, `kg query`/`blast`, or read-only git (the `git status`/`git log --oneline` checks in steps 4–5), and never re-gate between waves. Claude Code's built-in read-only commands don't prompt; this skill pre-approves `kg query`/`blast` and edits to `.workspace/local/session-state.md`; anything else the agents run goes through the normal permission prompt unless the user runs in auto mode or approves it. Re-gate **only** on real side effects: the writes/`git add`·`commit`·`push`/PR actions the dispatched agents perform, a merge conflict surfaced by **Conflict detection**, the batched worker questions, and the final **/certify**. See [lore/autonomy.md](../../lore/autonomy.md).

## Agent prompt — context contract (no context loss)

Spawned agents see NONE of this conversation. Every `Task` prompt — and every `agent()` prompt in `plan.workflow.js` — MUST be self-contained (see [lore/subagent-context.md](../../lore/subagent-context.md)):

```
Goal: implement task <N> — <one-line deliverable>.
Scope: files/paths in play: <exact list>. Out of scope: <...>.
Inputs: full task text from the plan (paste it — the `### Task N` block from plan.md, which carries the step's red/green/verify from plan.json), the Global Constraints, and the spec at .workspace/shared/specs/<feature>.md. FIRST read .workspace/local/session-state.md if it exists (current goal, decisions, blockers, artifact paths). Locate code with `kg query`/`kg blast`, not broad greps.
Constraints: follow TDD via /ward; conventions/lore: <...>; do not touch <deny paths>; definition of done: <...>.
Available magician skills: /conjure /blueprint /ward /unravel /certify /orchestrate /scrutinize /portal /seal /manifest /almanac /chronicle /magic /sentinel /accelerate /deploy /inscribe /autopsy
Return (bounded — distilled, never raw logs): STATUS: DONE | BLOCKED | NEEDS_CONTEXT; summary ≤ 1200 chars of what was implemented and committed; files_changed: <list>; commit: <sha or none>; obstacles: none, or one block per obstacle (lore/obstacles.md fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT). A question for the human goes in NEXT.
```

In a `Workflow`, encode the same return as the `agent()` `schema` (`maxLength` strings, `files_changed[]`, `obstacles[]`) — see [/weave's template](../weave/references/template.md).

## Handle results

- **DONE** — a claim, not proof: run the **Per-task quality loop** (below) and confirm the change from the VCS diff before recording it.
- **NEEDS_CONTEXT** — this is a context-completeness bug in the spawn prompt. Add the missing input and re-dispatch; don't guess for the agent.
- **BLOCKED** — assess the blocker, re-dispatch with more context, or escalate.
- **A question for the human** — a worker puts it in its Obstacles `NEXT` field and does not wait. Collect the questions of the whole wave, merge duplicates, and ask them in ONE `AskUserQuestion` after the wave returns. Never ask once per worker ([lore/obstacles.md](../../lore/obstacles.md)).

## Per-task quality loop — review before "done"

A subagent reporting `STATUS: DONE` is a claim, not evidence. Before you mark any task complete, confirm it from the VCS diff and put it through a **two-stage review** — see [lore/verification.md](../../lore/verification.md).

1. **Confirm from the diff, not the report.** Run `git show`/`git diff` for the task's commit(s) and read the actual change. The diff is the evidence a task landed — a subagent's "success" is not. If the diff is empty, or doesn't match the deliverable, the task is not done: re-dispatch with the gap named. (These are read-only git reads, which Claude Code doesn't prompt for — see **Autonomy** above.)
2. **Stage 1 — spec compliance.** Against the task's full text and `.workspace/shared/specs/<feature>.md`, does the change do *exactly* what the task specified — no more, no less? Flag missing requirements, scope creep, and silent deviations.
3. **Stage 2 — code quality.** Judge correctness, simplicity, and tests: does it hold on edge cases, is it the simplest thing that works, and are the tests real (proven RED→GREEN) and green? Prefer a fresh reviewer subagent (or [`/scrutinize`](../scrutinize/SKILL.md)) so no author bias carries over.
4. **Fix, then re-review.** For any **Critical** or **Important** finding, dispatch a *fresh* fix-subagent — self-contained prompt, same context contract — to resolve it, then re-run this loop on the new diff. Minor findings can be recorded and batched. A task counts as DONE only once its diff is clean on both stages.

**Keep moving.** Run this loop task-to-task without pausing to ask the human "should I continue?" — advancing through reviewed-and-clean tasks is exactly the autonomy the approved blueprint bought. Stop only on an unresolvable **BLOCKER**, a **merge conflict** (see **Conflict detection**), or all tasks done.

## Conflict detection

After each wave: `git status | grep -i conflict`. If conflicts are found, pause and resolve before continuing. (For parallel tasks that edit overlapping files, prefer worktree isolation per task.)

## Obstacles

**As a consumer** — every dispatched worker returns an Obstacles block on a non-clean run. Roll them up into one report kept apart from the deliverables (a blocked unit never reads as done), detect a pattern by a normalized BLOCKER + SCOPE signature, and memorize a confirmed pattern with `ctx learn --add "<signature -> workaround / next-action>"` in your own words — never verbatim worker text, secrets, or PII. Protocol: [lore/obstacles.md](../../lore/obstacles.md).

**As a producer** — if this skill runs as a dispatched unit and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) to the caller alongside whatever you completed; interactively, say the same in prose.

## Completion Signal

"Orchestrate complete. N tasks executed across M waves; cost ≈ $X (session delta). Run /scrutinize for review."

Cost clause: only with a reading at start and end, from `~/.claude/magician/status/${CLAUDE_SESSION_ID}.cost` (status line) or the mods band's `$.session.usage()`. Report the difference. Omit the clause otherwise. Never estimate it.
