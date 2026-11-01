---
name: blueprint
description: Converts an approved spec into a TDD task plan with a parallelism map and a visual walkthrough (plan.json → plan.md + plan.html) saved to a dated feature folder in .workspace/shared/plans/. Use after a spec is approved, before implementation.
allowed-tools: Read, Glob, AskUserQuestion, Bash(plan-render *), Bash(${CLAUDE_PLUGIN_ROOT}/tools/plan-render *), Bash(kg blast *), Edit(./.workspace/shared/plans/**)
argument-hint: "[spec-file-path] | review <plan-dir> | --static"
---

# /blueprint — Task Planning

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg`. If that is missing too, skip the `kg blast` step and leave `context.blast` out.

> **Bundled command:** if `plan-render` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/plan-render`. If that is missing too (Claude chat and Cowork ship no plugin tools), write `plan.md` only, in the single-file format of [references/plan-format-legacy.md](references/plan-format-legacy.md), and skip steps 4–5.

Convert an approved spec into one plan source, `plan.json`, and render two documents from it: `plan.md` (what `/orchestrate` and `/ward` execute) and `plan.html` (the walkthrough a person reviews).

- Schema, validation rules and the `plan.md` contract: [references/plan-schema.md](references/plan-schema.md)
- Worked example: [references/plan-example.json](references/plan-example.json)
- What the page shows, keyboard map: [references/walkthrough.md](references/walkthrough.md)

## Inputs Required

If the spec file path is not clear from context, ask: "Which spec should I plan from? (I'll use the most recent file in `.workspace/shared/specs/` if you don't specify.)" **End your turn. Wait for their reply (or proceed with most recent if context is unambiguous).**

`review <plan-dir>` reopens an existing plan: skip to step 5 (re-render) and step 7 (gate). `--static` is accepted and changes nothing in this version; it reserves the no-server mode for the live review loop.

## Process

1. **Read the spec** — every requirement, component and constraint. Read related research in `.workspace/shared/research/` (from `/magic`); if a key approach is unresearched, suggest `/magic` first. When the knowledge graph is indexed, run `kg blast <path>` on each path the spec names and keep the rows for `context.blast`; otherwise leave `blast` out — never estimate it.
2. **Map file structure** — every file to create or modify, with its responsibility, and the components they belong to.
3. **Decompose into tasks** — see Task Right-Sizing and Parallelism Rules below.
4. **Write `plan.json`** to `.workspace/shared/plans/YYYY-MM-DD-<feature>/plan.json` per the schema: `constraints` copied **verbatim** from the spec, one line each (every step inherits them); `waves` in order; one step per task with `red`, `green`, `verify`, `risk`, `effort`; `context.components`, `edges` and each step's `touches`, so the map has something to light up; `infographic` only where the spec, research or kg output gives real numbers — never invented. `version: 1`, `status: in_review`, every `review.status: pending`.
5. **Render** — `plan-render all <dir>/plan.json` (options `--theme light|dark|auto`, `--static`, `--mermaid`; the parts run alone as `check`, `md [-o]`, `html [-o]`, `diff <a.json> <b.json>`). It checks the plan, writes `plan.md` and `plan.html` next to it and snapshots the version into `history/`. Exit 2 means invalid JSON or violations, one line each: fix them in `plan.json` and re-run (1: file unreadable). Never hand-edit `plan.md` or `plan.html` — they are rendered.
6. **Tell the user** — one line: "Plan ready: N steps in W waves — open `<dir>/plan.html` (the walkthrough) · `<dir>/plan.md` (what /orchestrate executes)".
7. **Gate (use the AskUserQuestion tool — not plain prose)** — show the task list with parallelism annotations, then present the gate via **AskUserQuestion**, framed "Blueprint ready — lock it in?" with options:
   - **Approve → /orchestrate** — dispatch parallel agents (branch + commits happen there; push/PR still gate)
   - **Approve → /ward** — execute tasks one at a time
   - **Revise** — split / merge / reorder tasks (they describe the change, or paste `T7: …` lines from the page)
   - **Adjust scope** — add or drop tasks

   **End your turn at the AskUserQuestion call.** Act on the selection; treat any free-form "looks good / approved / yes" as Approve. On **Revise** or **Adjust scope**: edit `plan.json` only, bump `version` by 1, append `{v, changed}` to each touched step's `history`, set those steps' `review.status` to `changed`, re-run step 5 (it snapshots the previous version into `history/`), then gate again. On Approve, set `status: approved` and re-render once. This is a genuine decision gate — always the structured tool, never a bare sentence.

## Autonomy — approve the plan, then run

Steps 1–6 run as **one autonomous pass**: reading the spec and research, `kg blast`, writing `plan.json` and running `plan-render` (the paths and commands this skill pre-approves) need no confirmation question. The **only** gate is step 7. The downstream side effects — implementation edits, `git add`/`commit`/`push`, PR create/merge — are gated later by `/orchestrate` and `/ward`, not here. See [lore/autonomy.md](../../lore/autonomy.md).

## Task Right-Sizing

A task is the **smallest unit that carries its own test cycle and is worth a fresh reviewer's gate** — no finer:

- **Fold in** setup, scaffolding and docs — attach them to the task whose deliverable needs them.
- **Split** only where a reviewer could accept one task while rejecting its neighbour. Two pieces that always pass or fail together are one task.
- Every task ends with an **independently testable deliverable** — its `red` → `green` cycle is the proof. Effort 5–60 minutes; `risk.level` honest (`medium` for shared interfaces or data, `high` for anything without an easy rollback).

## Parallelism Rules

A step is `parallel: true` only if it does not write a file another parallel step of its wave reads or writes, and does not depend on types or functions defined in another parallel step. Integration tasks (wiring components) are always sequential. `plan-render check` refuses two parallel steps in one wave that modify the same file.

> Model/effort: for large multi-component specs, prefer the latest/code-optimal model and raise /effort to keep the decomposition and parallelism map sharp. See [lore/models.md](../../lore/models.md).

## Obstacles

If this skill runs as a dispatched unit (under /orchestrate, /weave, /manifest, /transmute, or another skill) and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return an Obstacles block to the caller, alongside whatever you did complete:

```
STATUS: BLOCKED | DEGRADED | NEEDS_CONTEXT
OBSTACLE: <one-line label of what blocked or degraded the task — the claim alone>
BLOCKER: <the specific, actionable cause — distilled, never a raw traceback or dumped log>
SEVERITY: Critical | High | Medium | Low
WORKAROUND: <what you did to proceed and what it leaves unverified; empty if still fully blocked>
RECURRENCE: First-seen | Recurring | Systemic
SCOPE: <this task only | likely hits sibling/downstream work too>
NEXT: <the action or decision the caller must make to clear it — retry with X, supply input Y, accept degraded, or escalate>
```

When invoked interactively by a human, surface the same obstacle in prose instead. Omit the block entirely on a clean run. See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Blueprint complete. <N> tasks planned (<P> parallel, <S> sequential) in <W> waves, saved to .workspace/shared/plans/<dir>/ (plan.json · plan.md · plan.html). Run /orchestrate to dispatch, or /ward task <N> to execute one by one."
