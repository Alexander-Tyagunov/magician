---
name: weave
description: Compose and run a large delivery as ONE native Workflow with magician's guardrails — use for big multi-item work: "implement these N stories/tickets/tasks", "deliver the epic", "build out all these features/endpoints", "migrate X across the codebase", "do all of the following", any batch/sweep of similar units. Picks the structure adaptively (per-item pipeline, parallel fan-out, orchestrator-worker, evaluator-optimizer) but always keeps TDD, kg grounding, certify, multi-lens review + adversarial verify, write gates, and no-context-loss. Use this instead of hand-rolling dozens of Agent calls.
allowed-tools: Workflow, Bash(kg:*), Task, Read, Write, AskUserQuestion
argument-hint: [goal · "implement these N tickets" · "migrate X across repo" · blueprint path]
---

# /weave — compose & run a delivery pipeline as one Workflow

When the task is "deliver many similar units" — N stories/tickets, a set of features/endpoints, a codebase-wide migration, a batch sweep — **don't hand-roll dozens of `Agent` calls.** Compose a single **native `Workflow`** that delivers all of them, and run it via the `Workflow` tool. The Workflow engine is the fast, deterministic fan-out (pipeline/parallel/orchestrator-worker) Claude reaches for anyway; this skill makes magician *own* it, with the guardrails baked in.

For a **single** task use `/ward` (TDD) directly; for executing an existing **blueprint** wave-by-wave use `/orchestrate`. `/weave` is for *adaptive, multi-unit delivery* where you compose the pipeline to the work.

The full, copy-and-adapt Workflow template (schemas, stages, kg grounding, the verify + remediate loop) is in **[references/template.md](references/template.md)**.

## Phase 0 — scope, ground, and plan (gate before running)

1. **Enumerate the units.** The N things to deliver (tickets, files, features). Pull ticket detail via `magician:jira` if relevant; read a blueprint from `.workspace/shared/plans/` if one exists.
2. **Ground in the codebase.** `kg check`; if no index, build one (`kg init`) — a shared graph is what keeps every worker cheap and consistent. For each unit, `kg query`/`kg blast` to scope the files it touches and its blast radius (pass these as `file:line` pointers into the worker prompts; never paste whole files).
3. **Pick the structure** (adaptive — see below) and the per-stage model/effort.
4. **Show the plan and get a go.** A large Workflow spawns many agents and costs real tokens. Use **AskUserQuestion**: list the units, the structure, the guardrails, and the rough agent/token scale. **Wait for approval before running.**

## Adaptive within guardrails

Choose the shape that fits (Anthropic agent patterns), tuning depth, agent count, and model/effort to the task:

- **Per-item `pipeline()`** *(default for N similar units)* — each unit flows implement → certify → review independently, no barrier; wall-clock = slowest single chain.
- **`parallel()` barrier** — when a step needs *all* prior results (cross-unit dedup, a consolidation pass, "0 found → skip").
- **Orchestrator-worker** — decompose first, then fan out workers over the decomposition.
- **Evaluator-optimizer loop** *(built into the default template)* — review → remediate → re-certify → re-review until clean, bounded by a round cap + `budget.remaining()`. The pipeline ships a clean changeset, not a to-do list.

You **may deviate** from any single skill's canned steps to fit the task. You may **not** drop these non-negotiables, whatever shape you pick:

<HARD-GATE>
1. **TDD per unit** — a failing test first, then green, then refactor (the `/ward` discipline).
2. **kg grounding** — workers locate code via `kg query`/`kg blast` and receive `file:line` pointers; no whole-file pastes.
3. **certify before "done"** — tests + types + lint + build pass for each unit before it counts as delivered.
4. **Review before ship, then remediate in-pipeline** — multi-lens (`magician:reviewer`/`sentinel`/`simplifier`/`verifier`) + adversarial verify on every Critical/High finding, then the bounded remediate loop (fix → re-certify → re-review) resolves confirmed findings before the pipeline reports done.
5. **Write gates** — the Workflow may read, implement on a branch/worktree, and test; it must **not** push, open/merge PRs, or do anything destructive without explicit user confirmation. Keep commits one-per-unit and surface them.
6. **No context loss** — every worker prompt is fully self-contained (Goal/Scope/Inputs/Constraints/Return per [lore/subagent-context.md](../../lore/subagent-context.md)); pass artifact **paths**, not dumps; workers return distilled summaries (~1–2k tokens), not raw output. Write a running `.workspace/local/session-state.md` (goal · done/remaining units · decisions · blockers · artifact paths) and have every worker read it first, so a compaction mid-run loses nothing.
</HARD-GATE>

## Run it

Adapt the template into a `Workflow({script})` call. Keep the script's `meta` a pure literal; group stages with `phase()`; use `schema` on every `agent()` whose result you branch on. Isolate file-mutating parallel workers with `isolation: 'worktree'` only when they'd otherwise collide. Read each phase's results before the next decision — you stay in the loop.

For very large or open-ended scope, run `/weave` in successive Workflows (one phase each) rather than one giant script, so you review between phases. For a long **unattended** delivery, pair with **`/goal`** so Claude keeps driving across turns until every unit is delivered + certified. Workflow stages run as background subagents (and may nest ~5 deep), so fan out and collect results as they land rather than blocking.

## Effort & models

Implement/verify stages on the latest code-optimal tier at high/xhigh effort; narrow lenses on small diffs can take a cheaper tier. Suggest a model upgrade rather than switching silently if the session is on an older one ([lore/models.md](../../lore/models.md)).

## Completion Signal

> "Weave complete: <N>/<N> units delivered (1 commit each), certified, reviewed (<C> criticals resolved over <R> remediation round(s)). Branch <name> — ready for you to push/PR (write-gated)."

Grounding for a unit's domain → `/magic`. Reviewing the whole changeset afterward → `/divine`. Shipping → `/seal` (gated).
